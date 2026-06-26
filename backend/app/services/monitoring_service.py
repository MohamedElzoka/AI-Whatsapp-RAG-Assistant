"""
Monitoring service: writes lightweight EventLog rows so the /analytics
endpoint and Streamlit dashboard can report on incoming messages, LLM
requests, errors, escalations, etc. without parsing log files.
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import EventLog, EventType
from app.utils.logger import get_logger

logger = get_logger(__name__)


def log_event(
    db: Session,
    event_type: EventType,
    detail: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    is_error: bool = False,
    commit: bool = True,
) -> None:
    try:
        event = EventLog(
            event_type=event_type,
            detail=json.dumps(detail) if detail else None,
            latency_ms=latency_ms,
            is_error=is_error,
        )
        db.add(event)
        if commit:
            db.commit()
    except Exception:
        logger.exception("Failed to write event log (event_type=%s)", event_type)
        db.rollback()
