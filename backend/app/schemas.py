"""
Pydantic schemas used for request validation and API responses.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Documents ----------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    uploaded_at: datetime
    indexed_at: Optional[datetime] = None


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    message: str


class ReindexResponse(BaseModel):
    status: str
    documents_queued: int


# ---------- Messages / Conversations ----------

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender: str
    content: str
    confidence_score: Optional[float] = None
    timestamp: datetime


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_phone: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    escalated: bool
    message_count: int
    last_message_preview: Optional[str] = None


class ConversationDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_phone: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    escalated: bool
    escalation_reason: Optional[str] = None
    messages: List[MessageOut]


class ConversationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    conversations: List[ConversationSummaryOut]


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)


class FeedbackListItem(BaseModel):
    id: str
    message_id: str
    conversation_id: str
    user_phone: str
    message_content: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


# ---------- Analytics ----------

class TimeseriesPoint(BaseModel):
    date: str
    count: int


class AnalyticsResponse(BaseModel):
    range_start: datetime
    range_end: datetime
    total_users: int
    total_conversations: int
    total_messages_in: int
    total_messages_out: int
    total_llm_requests: int
    total_errors: int
    escalation_count: int
    escalation_rate: float
    avg_confidence_score: Optional[float]
    feedback_avg_rating: Optional[float]
    feedback_count: int
    messages_per_day: List[TimeseriesPoint]
    errors_per_day: List[TimeseriesPoint]
    llm_requests_per_day: List[TimeseriesPoint]


# ---------- WhatsApp Webhook payloads (subset of Meta's schema) ----------

class WebhookVerification(BaseModel):
    hub_mode: Optional[str] = Field(None, alias="hub.mode")
    hub_challenge: Optional[str] = Field(None, alias="hub.challenge")
    hub_verify_token: Optional[str] = Field(None, alias="hub.verify_token")
