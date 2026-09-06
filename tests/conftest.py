import os

# Set required env vars before any app import triggers Settings() validation.
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
