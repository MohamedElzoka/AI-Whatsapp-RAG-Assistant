"""
Centralized application configuration.

All secrets and environment-specific values are read from environment
variables (typically supplied via a `.env` file and Docker Compose).
Nothing sensitive is ever hardcoded here.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- General ----
    APP_NAME: str = "AI WhatsApp Customer Support Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = ""

    # ---- Database (PostgreSQL) ----
    DATABASE_URL: str = (
        "postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_assistant"
    )

    # ---- Redis (conversation memory cache) ----
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_MEMORY_TTL_SECONDS: int = 60 * 60 * 6  # 6 hours of conversational memory
    REDIS_MEMORY_MAX_TURNS: int = 12  # how many past turns to keep per user

    # ---- Qdrant (vector database) ----
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "knowledge_base"
    EMBEDDING_DIMENSIONS: int = 1536  # text-embedding-3-small

    # ---- OpenAI ----
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_OUTPUT_TOKENS: int = 600

    # ---- RAG / escalation tuning ----
    RAG_TOP_K: int = 5
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    SIMILARITY_THRESHOLD: float = 0.02  # below this -> treated as "no relevant doc"
    CONFIDENCE_ESCALATION_THRESHOLD: float = 0.45  # below this -> escalate to human

    # ---- WhatsApp Cloud API ----
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "change-me-verify-token"
    WHATSAPP_APP_SECRET: str = ""  # used to verify X-Hub-Signature-256
    WHATSAPP_API_VERSION: str = "v20.0"
    WHATSAPP_GRAPH_BASE_URL: str = "https://graph.facebook.com"
    HUMAN_ESCALATION_PHONE: str | None = None  # optional internal number to notify

    # ---- Security ----
    SECRET_KEY: str = "change-this-in-production"
    FIELD_ENCRYPTION_KEY: str = ""  # Fernet key, see app/security.py
    ADMIN_API_KEY: str = "change-this-admin-api-key"  # protects dashboard-facing routes
    CORS_ALLOW_ORIGINS: List[str] = ["*"]

    # ---- File uploads ----
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "/app/logs"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
