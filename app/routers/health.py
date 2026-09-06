from fastapi import APIRouter

from app.cache import get_redis
from app.config import get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    deps = {}

    try:
        redis_client = await get_redis()
        await redis_client.ping()
        deps["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        deps["redis"] = f"error: {exc}"

    try:
        from app.vectorstore import get_vector_store

        get_vector_store()
        deps["vector_store"] = "ok"
    except Exception as exc:  # noqa: BLE001
        deps["vector_store"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in deps.values()) else "degraded"
    return HealthResponse(status=overall, version="1.0.0", dependencies=deps)


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe for k8s — no dependency checks, just process health."""
    return {"status": "alive"}
