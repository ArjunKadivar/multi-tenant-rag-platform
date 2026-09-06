import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_liveness_probe(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.anyio
async def test_query_without_api_key_is_rejected(client):
    response = await client.post("/api/v1/query", json={"query": "What is RAG?"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_tenant_creation_requires_admin_key(client):
    response = await client.post("/api/v1/tenants", json={"name": "acme-corp"})
    assert response.status_code == 403


@pytest.fixture
def anyio_backend():
    return "asyncio"
