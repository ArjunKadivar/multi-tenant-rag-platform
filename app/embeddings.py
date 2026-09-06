"""
Embedding provider abstraction so switching from OpenAI to a local
HuggingFace model is a config change, not a code change.
"""
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.config import get_settings


@lru_cache
def get_embedding_client() -> Embeddings:
    settings = get_settings()

    if settings.EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=settings.EMBEDDING_MODEL, api_key=settings.OPENAI_API_KEY)

    if settings.EMBEDDING_PROVIDER == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    raise ValueError(f"Unsupported embedding provider: {settings.EMBEDDING_PROVIDER}")
