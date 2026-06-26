"""
FastAPI application entrypoint.

Wires together routers, startup hooks (DB table + Qdrant collection
bootstrap), CORS, and a health check used by Docker/monitoring.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import analytics, conversations, documents, webhook
from app.utils.logger import get_logger, setup_logging
from app.vectorstore import ensure_collection

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (environment=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    init_db()
    try:
        ensure_collection()
    except Exception:
        logger.exception(
            "Could not reach Qdrant on startup; it may still be initializing. "
            "Document indexing/search will retry on first use."
        )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered WhatsApp customer support assistant using Retrieval-"
        "Augmented Generation (RAG), GPT-4o, Qdrant, PostgreSQL, and Redis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(analytics.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/", tags=["health"])
def root():
    return {
        "service": settings.APP_NAME,
        "docs": "/docs",
        "health": "/health",
    }
