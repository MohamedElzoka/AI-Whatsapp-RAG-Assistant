"""
WhatsApp Cloud API webhook endpoints.

GET  /webhook  -> Meta's one-time webhook verification handshake
POST /webhook  -> inbound message delivery
"""
import time

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import EventType, SenderType
from app.security import verify_whatsapp_signature
from app.services import conversation_service, escalation_service, monitoring_service, rag_service
from app.services.whatsapp_service import InboundMessage, mark_message_as_read, parse_inbound_payload, send_text_message
from app.utils.logger import get_logger

router = APIRouter(tags=["webhook"])
logger = get_logger(__name__)


@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta calls this once when you configure the webhook URL in the App
    Dashboard (and again any time you change it). We must echo back
    hub.challenge if hub.verify_token matches our configured secret.

    Query params use dots (hub.mode, hub.challenge, hub.verify_token) so
    they're read directly off the raw query string rather than declared
    as typed FastAPI parameters.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge or "", media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed.")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
):
    raw_body = await request.body()

    if not verify_whatsapp_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    payload = await request.json()
    inbound_messages = parse_inbound_payload(payload)

    for message in inbound_messages:
        # Process each message in the background so we can return 200 to
        # Meta immediately (they retry aggressively on slow/failed responses).
        background_tasks.add_task(process_inbound_message, message)

    return {"status": "received", "message_count": len(inbound_messages)}


def process_inbound_message(message: InboundMessage) -> None:
    """
    Runs in a background task: persists the message, runs the RAG
    pipeline, sends the reply back over WhatsApp, and records monitoring
    events. Uses its own DB session since it runs outside the request scope.
    """
    db: Session = SessionLocal()
    start_time = time.perf_counter()

    try:
        monitoring_service.log_event(
            db,
            EventType.message_received,
            detail={"from": message.from_phone, "whatsapp_message_id": message.whatsapp_message_id},
        )

        mark_message_as_read(message.whatsapp_message_id)

        user = conversation_service.get_or_create_user(
            db, phone=message.from_phone, display_name=message.profile_name
        )
        conversation = conversation_service.get_or_create_active_conversation(db, user)

        conversation_service.save_message(
            db,
            conversation,
            sender=SenderType.customer,
            content=message.text,
            whatsapp_message_id=message.whatsapp_message_id,
        )

        rag_result = rag_service.answer_question(user_phone=user.phone, question=message.text)

        monitoring_service.log_event(
            db,
            EventType.llm_request,
            detail={"phone": user.phone, "confidence": rag_result.confidence},
            latency_ms=rag_result.llm_latency_ms,
        )

        reply_text = rag_result.answer
        if rag_result.should_escalate:
            reply_text = (
                f"{rag_result.answer}\n\n"
                "I've also flagged this for one of our team members to follow up "
                "with you shortly."
            )
            conversation_service.mark_conversation_escalated(
                db, conversation, reason=rag_result.escalation_reason or "unknown"
            )
            monitoring_service.log_event(
                db,
                EventType.escalation,
                detail={
                    "phone": user.phone,
                    "reason": rag_result.escalation_reason,
                    "question": message.text,
                },
            )
            escalation_service.notify_human_agent(
                customer_phone=user.phone,
                reason=rag_result.escalation_reason or "unknown",
                last_question=message.text,
            )

        assistant_message = conversation_service.save_message(
            db,
            conversation,
            sender=SenderType.assistant,
            content=reply_text,
            confidence_score=rag_result.confidence,
            retrieved_sources=rag_result.sources,
        )

        send_text_message(to_phone=user.phone, body=reply_text)

        logger.info(
            "Processed message from %s in %.0fms (escalate=%s, confidence=%.2f, msg_id=%s)",
            user.phone,
            (time.perf_counter() - start_time) * 1000,
            rag_result.should_escalate,
            rag_result.confidence,
            assistant_message.id,
        )

    except Exception as exc:
        logger.exception("Error processing inbound WhatsApp message")
        monitoring_service.log_event(
            db,
            EventType.error,
            detail={"context": "process_inbound_message", "error": str(exc)},
            is_error=True,
        )
        try:
            send_text_message(
                to_phone=message.from_phone,
                body=(
                    "Sorry, something went wrong on our end processing your message. "
                    "Our team has been notified and will follow up shortly."
                ),
            )
        except Exception:
            logger.exception("Failed to send fallback error message to user")
    finally:
        db.close()
from pydantic import BaseModel

class TestMessage(BaseModel):
    phone: str = "201000000000"
    text: str


@router.post("/test-chat")
async def test_chat(data: TestMessage):
    rag_result = rag_service.answer_question(
        user_phone=data.phone,
        question=data.text,
    )

    return {
        "question": data.text,
        "answer": rag_result.answer,
        "confidence": rag_result.confidence,
        "sources": rag_result.sources,
        "should_escalate": rag_result.should_escalate,
    }
