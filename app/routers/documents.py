import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Document, Tenant
from app.schemas import DocumentStatus, IngestResponse
from app.security import get_current_tenant
from app.workers import ingest_document_task

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_document(
    file: UploadFile,
    chunk_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}")

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, "File exceeds 20MB limit")

    text = _extract_text(raw_bytes, ext)
    if not text.strip():
        raise HTTPException(422, "No extractable text found in file")

    document_id = str(uuid.uuid4())
    doc = Document(id=document_id, tenant_id=tenant.id, source_name=file.filename, status="queued")
    db.add(doc)
    await db.commit()

    ingest_document_task.delay(
        document_id=document_id,
        tenant_id=tenant.id,
        text=text,
        source_name=file.filename,
        strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return IngestResponse(document_id=document_id, chunks_created=0, status="queued")


@router.get("/{document_id}", response_model=DocumentStatus)
async def get_document_status(
    document_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatus:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == tenant.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Document not found")
    return DocumentStatus(
        document_id=doc.id,
        source_name=doc.source_name,
        status=doc.status,
        chunks_created=doc.chunks_created,
        created_at=doc.created_at,
    )


def _extract_text(raw_bytes: bytes, ext: str) -> str:
    if ext == ".pdf":
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return raw_bytes.decode("utf-8", errors="ignore")
