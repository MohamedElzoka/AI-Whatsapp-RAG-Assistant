"""
Human escalation logic.

Per the design doc, escalation triggers when ANY of the following hold:
  - Similarity score of the best matching chunk is below threshold
  - No relevant documents were found at all
  - The LLM's own confidence score is too low
"""
from dataclasses import dataclass

from app.config import settings
from app.services import whatsapp_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: str | None = None


def evaluate_escalation(
    top_similarity_score: float | None,
    llm_confidence: float,
) -> EscalationDecision:
    if top_similarity_score is None:
        return EscalationDecision(True, "no_relevant_documents_found")

    if top_similarity_score < settings.SIMILARITY_THRESHOLD:
        return EscalationDecision(True, "similarity_score_below_threshold")

    if llm_confidence < settings.CONFIDENCE_ESCALATION_THRESHOLD:
        return EscalationDecision(True, "low_llm_confidence")

    return EscalationDecision(False, None)


def notify_human_agent(customer_phone: str, reason: str, last_question: str) -> None:
    """
    Best-effort notification to an internal staff WhatsApp number, if
    configured. Failure to notify must never block the customer-facing
    response flow.
    """
    if not settings.HUMAN_ESCALATION_PHONE:
        logger.info(
            "Escalation triggered (reason=%s) but HUMAN_ESCALATION_PHONE is not "
            "configured; skipping human notification.",
            reason,
        )
        return

    try:
        whatsapp_service.send_text_message(
            to_phone=settings.HUMAN_ESCALATION_PHONE,
            body=(
                "Customer support escalation\n"
                f"Reason: {reason}\n"
                f"Customer: {customer_phone}\n"
                f"Question: {last_question}"
            ),
        )
    except Exception:
        logger.exception("Failed to notify human agent of escalation")
