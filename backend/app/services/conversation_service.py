"""
Conversation persistence helpers: get-or-create user/conversation, and
store inbound/outbound messages.

A conversation is considered "active" and reused if the user has an open
conversation; otherwise a new one is started. This keeps each WhatsApp
user's history organized into logical sessions for the dashboard.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Conversation, ConversationStatus, Message, SenderType, User


def get_or_create_user(db: Session, phone: str, display_name: Optional[str] = None) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        user.last_seen_at = datetime.utcnow()
        if display_name and not user.display_name:
            user.display_name = display_name
        db.commit()
        db.refresh(user)
        return user

    user = User(phone=phone, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_active_conversation(db: Session, user: User) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.status == ConversationStatus.open)
        .order_by(Conversation.started_at.desc())
        .first()
    )
    if conversation:
        return conversation

    conversation = Conversation(user_id=user.id, status=ConversationStatus.open)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def save_message(
    db: Session,
    conversation: Conversation,
    sender: SenderType,
    content: str,
    whatsapp_message_id: Optional[str] = None,
    confidence_score: Optional[float] = None,
    retrieved_sources: Optional[list[dict]] = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        sender=sender,
        content=content,
        whatsapp_message_id=whatsapp_message_id,
        confidence_score=confidence_score,
        retrieved_sources=json.dumps(retrieved_sources) if retrieved_sources else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def mark_conversation_escalated(db: Session, conversation: Conversation, reason: str) -> None:
    conversation.escalated = True
    conversation.escalation_reason = reason
    conversation.status = ConversationStatus.escalated
    db.commit()
