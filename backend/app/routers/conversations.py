"""
Conversation inspection + feedback endpoints (admin/dashboard-facing).

  GET  /conversations              - paginated list with summaries
  GET  /conversations/{id}         - full message thread for one conversation
  POST /conversations/messages/{message_id}/feedback - record customer feedback
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Conversation, EventType, Feedback, Message, SenderType, User
from app.schemas import (
    ConversationDetailOut,
    ConversationListResponse,
    ConversationSummaryOut,
    FeedbackCreate,
    FeedbackListItem,
    FeedbackOut,
    MessageOut,
)
from app.security import require_admin_api_key
from app.services import monitoring_service

router = APIRouter(
    prefix="/conversations", tags=["conversations"], dependencies=[Depends(require_admin_api_key)]
)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    phone: str | None = Query(None, description="Filter by customer phone number"),
    status_filter: str | None = Query(None, alias="status"),
    escalated_only: bool = Query(False),
):
    query = db.query(Conversation).join(User)

    if phone:
        query = query.filter(User.phone.ilike(f"%{phone}%"))
    if status_filter:
        query = query.filter(Conversation.status == status_filter)
    if escalated_only:
        query = query.filter(Conversation.escalated.is_(True))

    total = query.count()
    conversations = (
        query.order_by(Conversation.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    summaries = []
    for conv in conversations:
        message_count = (
            db.query(func.count(Message.id)).filter(Message.conversation_id == conv.id).scalar()
        )
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        summaries.append(
            ConversationSummaryOut(
                id=conv.id,
                user_phone=conv.user.phone,
                started_at=conv.started_at,
                ended_at=conv.ended_at,
                status=conv.status.value,
                escalated=conv.escalated,
                message_count=message_count or 0,
                last_message_preview=(last_message.content[:140] if last_message else None),
            )
        )

    return ConversationListResponse(
        total=total, page=page, page_size=page_size, conversations=summaries
    )


@router.get("/feedback/all", response_model=list[FeedbackListItem])
def list_feedback(db: Session = Depends(get_db), min_rating: int | None = None, max_rating: int | None = None):
    query = (
        db.query(Feedback, Message, Conversation, User)
        .join(Message, Feedback.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
    )
    if min_rating is not None:
        query = query.filter(Feedback.rating >= min_rating)
    if max_rating is not None:
        query = query.filter(Feedback.rating <= max_rating)

    rows = query.order_by(Feedback.created_at.desc()).all()

    return [
        FeedbackListItem(
            id=feedback.id,
            message_id=message.id,
            conversation_id=conversation.id,
            user_phone=user.phone,
            message_content=message.content,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )
        for feedback, message, conversation, user in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages), joinedload(Conversation.user))
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    return ConversationDetailOut(
        id=conversation.id,
        user_phone=conversation.user.phone,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        status=conversation.status.value,
        escalated=conversation.escalated,
        escalation_reason=conversation.escalation_reason,
        messages=[MessageOut.model_validate(m) for m in conversation.messages],
    )


@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(message_id: str, payload: FeedbackCreate, db: Session = Depends(get_db)):
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.sender != SenderType.assistant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback can only be left on assistant-generated messages.",
        )

    existing = db.query(Feedback).filter(Feedback.message_id == message_id).first()
    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        db.commit()
        db.refresh(existing)
        feedback = existing
    else:
        feedback = Feedback(message_id=message_id, rating=payload.rating, comment=payload.comment)
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

    monitoring_service.log_event(
        db,
        EventType.feedback_received,
        detail={"message_id": message_id, "rating": payload.rating},
    )

    return FeedbackOut.model_validate(feedback)
