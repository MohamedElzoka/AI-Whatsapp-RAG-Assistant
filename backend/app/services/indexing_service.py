"""
Indexing service: takes a Document DB row, extracts + chunks its text,
embeds the chunks, and upserts them into Qdrant. Used both by the
single-document upload flow and the full knowledge-base reindex flow.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Document, DocumentStatus, EventType
from app.services import monitoring_service
from app.services.document_processor import chunk_text, extract_text
from app.services.embedding_service import embed_texts
from app.utils.logger import get_logger
from app.vectorstore import delete_by_document_id, upsert_chunks

logger = get_logger(__name__)


def index_document(db: Session, document: Document) -> None:
    """Process a single document end-to-end and update its status in place."""
    document.status = DocumentStatus.indexing
    document.error_message = None
    db.commit()

    try:
        raw_text = extract_text(document.file_path, document.file_type)
        chunks = chunk_text(raw_text)

        if not chunks:
            raise ValueError("No extractable text found in document.")

        # Remove any previously indexed vectors for this document first
        # (relevant on re-upload / re-index of the same document id).
        delete_by_document_id(document.id)

        embeddings = embed_texts(chunks)
        written = upsert_chunks(document.id, document.filename, chunks, embeddings)

        document.status = DocumentStatus.indexed
        document.chunk_count = written
        document.indexed_at = datetime.utcnow()
        db.commit()

        monitoring_service.log_event(
            db,
            EventType.document_indexed,
            detail={"document_id": document.id, "filename": document.filename, "chunks": written},
        )
        logger.info("Indexed document %s (%s chunks)", document.filename, written)

    except Exception as exc:
        logger.exception("Failed to index document %s", document.filename)
        document.status = DocumentStatus.failed
        document.error_message = str(exc)
        db.commit()
        monitoring_service.log_event(
            db,
            EventType.error,
            detail={"context": "document_indexing", "document_id": document.id, "error": str(exc)},
            is_error=True,
        )
