"""
Document management endpoints (admin/dashboard-facing, protected by the
X-Admin-Api-Key header):

  POST /documents/upload   - upload a PDF/DOCX/TXT and index it
  POST /documents/reindex  - rebuild the entire vector index from scratch
  GET  /documents          - list all uploaded documents
"""
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document, DocumentStatus
from app.schemas import DocumentOut, DocumentUploadResponse, ReindexResponse
from app.security import require_admin_api_key
from app.services.indexing_service import index_document
from app.vectorstore import recreate_collection
from app.utils.logger import get_logger

router = APIRouter(
    prefix="/documents", tags=["documents"], dependencies=[Depends(require_admin_api_key)]
)
logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    extension = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{extension}'. Allowed: PDF, DOCX, TXT.",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    document_id = str(uuid.uuid4())
    stored_filename = f"{document_id}.{extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    document = Document(
        id=document_id,
        filename=file.filename,
        file_path=file_path,
        file_type=extension,
        status=DocumentStatus.pending,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Index in the background so the upload request returns immediately.
    background_tasks.add_task(_index_document_background, document.id)

    return DocumentUploadResponse(
        document=DocumentOut.model_validate(document),
        message="Document uploaded and queued for indexing.",
    )


def _index_document_background(document_id: str) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            index_document(db, document)
    finally:
        db.close()


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [DocumentOut.model_validate(d) for d in documents]


@router.post("/reindex", response_model=ReindexResponse)
def reindex_knowledge_base(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Rebuild the entire Qdrant collection from every document currently
    stored on disk. Useful after tuning chunk size/overlap or recovering
    from a vector store reset.
    """
    documents = db.query(Document).all()
    if not documents:
        return ReindexResponse(status="no_documents", documents_queued=0)

    recreate_collection()

    for document in documents:
        document.status = DocumentStatus.pending
        document.chunk_count = 0
    db.commit()

    for document in documents:
        background_tasks.add_task(_index_document_background, document.id)

    return ReindexResponse(status="reindex_started", documents_queued=len(documents))
