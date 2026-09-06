from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str
    plan: Literal["free", "pro", "enterprise"] = "free"


class TenantOut(BaseModel):
    id: str
    name: str
    plan: str
    api_key: str
    created_at: datetime


class IngestRequest(BaseModel):
    """Metadata accompanying an uploaded document."""
    source_name: str
    chunk_strategy: Optional[Literal["recursive", "semantic", "fixed"]] = None
    chunk_size: Optional[int] = Field(default=None, ge=100, le=4000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0, le=1000)
    tags: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int
    status: Literal["queued", "processing", "completed", "failed"]


class DocumentStatus(BaseModel):
    document_id: str
    source_name: str
    status: str
    chunks_created: int
    created_at: datetime


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    filters: dict = Field(default_factory=dict)
    stream: bool = False


class SourceChunk(BaseModel):
    document_id: str
    source_name: str
    chunk_text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    latency_ms: float
    cached: bool = False


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: dict
