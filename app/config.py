"""
Central application configuration.

All values are sourced from environment variables (12-factor style) so the
same image can be promoted from dev -> staging -> prod without code changes.
See `.env.example` for the full list of supported variables.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "rag-platform"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # --- Security ---
    # Master key used only to mint/validate tenant API keys via the admin route.
    ADMIN_API_KEY: str = Field(..., description="Bootstrap admin key, rotate via secrets manager")
    JWT_SECRET: str = Field(..., description="Used only if JWT auth mode is enabled")
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Database (tenant / document metadata, API keys) ---
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@postgres:5432/rag_platform"

    # --- Cache / task queue ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Vector store ---
    VECTOR_BACKEND: Literal["qdrant", "chroma"] = "qdrant"
    QDRANT_URL: str = "http://qdrant:6333"
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # --- Embeddings / LLM ---
    EMBEDDING_PROVIDER: Literal["openai", "huggingface"] = "openai"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""

    # --- Chunking defaults (overridable per-request) ---
    DEFAULT_CHUNK_SIZE: int = 800
    DEFAULT_CHUNK_OVERLAP: int = 120
    DEFAULT_CHUNK_STRATEGY: Literal["recursive", "semantic", "fixed"] = "recursive"

    # --- Retrieval ---
    DEFAULT_TOP_K: int = 5
    RERANK_ENABLED: bool = True

    # --- Observability ---
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
