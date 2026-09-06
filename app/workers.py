"""
Celery worker: document ingestion runs off the request/response cycle.

Why: chunking + embedding a large PDF can take seconds to minutes. Doing
that inline would block the API worker and time out client requests, so the
endpoint just enqueues the job and returns a document_id + "queued" status
immediately (see app/routers/documents.py).
"""
import asyncio
import logging

from celery import Celery
from sqlalchemy import select

from app.chunking import chunk_text
from app.config import get_settings
from app.db import AsyncSessionLocal
from app.metrics import CHUNKS_CREATED, INGESTION_COUNT
from app.models import Document
from app.vectorstore import get_vector_store

settings = get_settings()
logger = logging.getLogger(__name__)

celery_app = Celery("rag_platform", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery_app.task(name="ingest_document", bind=True, max_retries=3, default_retry_delay=30)
def ingest_document_task(
    self,
    document_id: str,
    tenant_id: str,
    text: str,
    source_name: str,
    strategy: str | None,
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> None:
    try:
        asyncio.run(
            _ingest(document_id, tenant_id, text, source_name, strategy, chunk_size, chunk_overlap)
        )
    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        INGESTION_COUNT.labels(tenant_id=tenant_id, status="failed").inc()
        raise self.retry(exc=exc)


async def _ingest(
    document_id: str,
    tenant_id: str,
    text: str,
    source_name: str,
    strategy: str | None,
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> None:
    chunks = chunk_text(text, strategy=strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunk_strategy = chunks[0].metadata["strategy"] if chunks else (strategy or "recursive")

    store = get_vector_store()
    store.upsert(
        tenant_id=tenant_id,
        document_id=document_id,
        chunks=[c.text for c in chunks],
        metadatas=[{"source_name": source_name, "chunk_index": c.index} for c in chunks],
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one()
        doc.status = "completed"
        doc.chunks_created = len(chunks)
        await session.commit()

    CHUNKS_CREATED.labels(tenant_id=tenant_id, strategy=chunk_strategy).inc(len(chunks))
    INGESTION_COUNT.labels(tenant_id=tenant_id, status="completed").inc()
