"""
Multi-tenant API key authentication + per-tenant rate limiting.

Design notes:
- API keys are never stored in plaintext; only a SHA-256 hash is persisted,
  mirroring how Stripe/GitHub handle personal access tokens.
- Rate limiting uses a Redis sliding-window counter so it works correctly
  across multiple app replicas (no in-memory state).
"""
import hashlib
import secrets
import time

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import get_redis
from app.config import get_settings
from app.db import get_db
from app.models import Tenant

settings = get_settings()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def generate_api_key() -> str:
    return f"rag_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_tenant(
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")

    result = await db.execute(select(Tenant).where(Tenant.api_key_hash == hash_api_key(api_key)))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    await _enforce_rate_limit(tenant.id)
    return tenant


async def require_admin(admin_key: str | None = Security(admin_key_header)) -> None:
    if not admin_key or not secrets.compare_digest(admin_key, settings.ADMIN_API_KEY):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid admin key")


async def _enforce_rate_limit(tenant_id: str) -> None:
    redis = await get_redis()
    window = int(time.time() // 60)
    key = f"ratelimit:{tenant_id}:{window}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 60)

    if current > settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded: {settings.RATE_LIMIT_PER_MINUTE} requests/minute",
        )
