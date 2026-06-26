"""
Analytics endpoint: aggregates EventLog, Message, Conversation, and
Feedback data into the KPIs and timeseries the Streamlit dashboard charts.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Conversation, EventLog, EventType, Feedback, Message, SenderType, User
from app.schemas import AnalyticsResponse, TimeseriesPoint
from app.security import require_admin_api_key

router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_admin_api_key)]
)


def _daily_counts(db: Session, event_type: EventType, start: datetime, end: datetime, is_error: bool | None = None):
    query = db.query(
        cast(EventLog.created_at, Date).label("day"), func.count(EventLog.id).label("count")
    ).filter(
        EventLog.event_type == event_type,
        EventLog.created_at >= start,
        EventLog.created_at <= end,
    )
    if is_error is not None:
        query = query.filter(EventLog.is_error.is_(is_error))

    rows = query.group_by("day").order_by("day").all()
    return [TimeseriesPoint(date=str(row.day), count=row.count) for row in rows]


@router.get("", response_model=AnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
):
    range_end = datetime.utcnow()
    range_start = range_end - timedelta(days=days)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_conversations = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.started_at >= range_start)
        .scalar()
        or 0
    )

    total_messages_in = (
        db.query(func.count(Message.id))
        .filter(Message.sender == SenderType.customer, Message.timestamp >= range_start)
        .scalar()
        or 0
    )
    total_messages_out = (
        db.query(func.count(Message.id))
        .filter(Message.sender == SenderType.assistant, Message.timestamp >= range_start)
        .scalar()
        or 0
    )

    total_llm_requests = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.event_type == EventType.llm_request, EventLog.created_at >= range_start)
        .scalar()
        or 0
    )
    total_errors = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.is_error.is_(True), EventLog.created_at >= range_start)
        .scalar()
        or 0
    )
    escalation_count = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.event_type == EventType.escalation, EventLog.created_at >= range_start)
        .scalar()
        or 0
    )

    escalation_rate = (
        round(escalation_count / total_conversations, 4) if total_conversations else 0.0
    )

    avg_confidence_score = (
        db.query(func.avg(Message.confidence_score))
        .filter(Message.sender == SenderType.assistant, Message.timestamp >= range_start)
        .scalar()
    )

    feedback_avg_rating = db.query(func.avg(Feedback.rating)).scalar()
    feedback_count = db.query(func.count(Feedback.id)).scalar() or 0

    return AnalyticsResponse(
        range_start=range_start,
        range_end=range_end,
        total_users=total_users,
        total_conversations=total_conversations,
        total_messages_in=total_messages_in,
        total_messages_out=total_messages_out,
        total_llm_requests=total_llm_requests,
        total_errors=total_errors,
        escalation_count=escalation_count,
        escalation_rate=escalation_rate,
        avg_confidence_score=round(avg_confidence_score, 4) if avg_confidence_score else None,
        feedback_avg_rating=round(feedback_avg_rating, 2) if feedback_avg_rating else None,
        feedback_count=feedback_count,
        messages_per_day=_daily_counts(db, EventType.message_received, range_start, range_end),
        errors_per_day=_daily_counts(db, EventType.error, range_start, range_end, is_error=True),
        llm_requests_per_day=_daily_counts(db, EventType.llm_request, range_start, range_end),
    )
