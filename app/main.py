import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.config import get_settings
from app.db import init_models
from app.logging_config import configure_logging
from app.routers import documents, health, query, tenants

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "development":
        await init_models()  # dev convenience; use Alembic migrations in prod
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title="RAG Platform API",
    description="Multi-tenant Retrieval-Augmented Generation as a service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()

    response: Response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "duration_ms": round(duration_ms, 2),
            "status_code": response.status_code,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(tenants.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(query.router, prefix=settings.API_V1_PREFIX)
