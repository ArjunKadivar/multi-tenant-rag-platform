"""
Redis-backed caching for query results and the rate limiter.

Caching RAG answers matters more than people expect: enterprise FAQs and
support queries are heavily repeated, and skipping the LLM call on a cache
hit is the single biggest cost lever available without touching quality.
"""
import hashlib
import json

import redis.asyncio as redis

from app.config import get_settings

_redis_client: redis.Redis | None = None

CACHE_TTL_SECONDS = 60 * 30  # 30 minutes; tune per tenant plan if needed


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _cache_key(tenant_id: str, query: str, top_k: int, filters: dict) -> str:
    raw = f"{tenant_id}:{query}:{top_k}:{json.dumps(filters, sort_keys=True)}"
    return f"query_cache:{hashlib.sha256(raw.encode()).hexdigest()}"


async def get_cached_answer(tenant_id: str, query: str, top_k: int, filters: dict) -> dict | None:
    client = await get_redis()
    raw = await client.get(_cache_key(tenant_id, query, top_k, filters))
    return json.loads(raw) if raw else None


async def set_cached_answer(tenant_id: str, query: str, top_k: int, filters: dict, payload: dict) -> None:
    client = await get_redis()
    await client.set(_cache_key(tenant_id, query, top_k, filters), json.dumps(payload), ex=CACHE_TTL_SECONDS)
