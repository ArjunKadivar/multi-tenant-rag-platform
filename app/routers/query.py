import time

from fastapi import APIRouter, Depends

from app.cache import get_cached_answer, set_cached_answer
from app.metrics import QUERY_COUNT, QUERY_LATENCY
from app.models import Tenant
from app.rag_chain import answer_query
from app.schemas import QueryRequest, QueryResponse, SourceChunk
from app.security import get_current_tenant

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(payload: QueryRequest, tenant: Tenant = Depends(get_current_tenant)) -> QueryResponse:
    start = time.perf_counter()

    cached = await get_cached_answer(tenant.id, payload.query, payload.top_k or 0, payload.filters)
    if cached:
        QUERY_COUNT.labels(tenant_id=tenant.id, cached="true").inc()
        return QueryResponse(**cached, cached=True)

    result = await answer_query(tenant.id, payload.query, payload.top_k, payload.filters)

    response = QueryResponse(
        answer=result["answer"],
        sources=[SourceChunk(**s) for s in result["sources"]],
        latency_ms=result["latency_ms"],
        cached=False,
    )

    await set_cached_answer(
        tenant.id, payload.query, payload.top_k or 0, payload.filters, response.model_dump(exclude={"cached"})
    )

    QUERY_COUNT.labels(tenant_id=tenant.id, cached="false").inc()
    QUERY_LATENCY.labels(tenant_id=tenant.id).observe(time.perf_counter() - start)
    return response
