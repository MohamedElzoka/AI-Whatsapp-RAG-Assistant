"""
ORM models.

Tables (per design doc):
    Users, Conversations, Messages, Feedback, Documents
Plus a supporting EventLog table used to power /analytics
(incoming messages, LLM requests, errors, etc.) without scraping log files.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class SenderType(str, enum.Enum):
    customer = "customer"
    assistant = "assistant"
    human_agent = "human_agent"
    system = "system"


class ConversationStatus(str, enum.Enum):
    open = "open"
    escalated = "escalated"
    closed = "closed"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    indexing = "indexing"
    indexed = "indexed"
    failed = "failed"


class EventType(str, enum.Enum):
    message_received = "message_received"
    llm_request = "llm_request"
    error = "error"
    escalation = "escalation"
    document_indexed = "document_indexed"
    feedback_received = "feedback_received"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    phone = Column(String(32), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(
        Enum(ConversationStatus), default=ConversationStatus.open, nullable=False
    )
    escalated = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(String(255), nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.timestamp",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    conversation_id = Column(
        UUID(as_uuid=False), ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender = Column(Enum(SenderType), nullable=False)
    content = Column(Text, nullable=False)
    whatsapp_message_id = Column(String(128), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)
    retrieved_sources = Column(Text, nullable=True)  # JSON-encoded list of doc chunks used
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = relationship("Conversation", back_populates="messages")
    feedback = relationship(
        "Feedback", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    message_id = Column(
        UUID(as_uuid=False), ForeignKey("messages.id"), nullable=False, unique=True, index=True
    )
    rating = Column(Integer, nullable=False)  # e.g. 1 = thumbs down, 5 = thumbs up (1-5 scale)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="feedback")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(16), nullable=False)  # pdf | docx | txt
    status = Column(Enum(DocumentStatus), default=DocumentStatus.pending, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    indexed_at = Column(DateTime, nullable=True)


class EventLog(Base):
    """Lightweight event stream used for the /analytics endpoint and dashboard."""

    __tablename__ = "event_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    event_type = Column(Enum(EventType), nullable=False, index=True)
    detail = Column(Text, nullable=True)  # JSON-encoded extra context
    latency_ms = Column(Float, nullable=True)
    is_error = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
