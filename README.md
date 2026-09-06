# RAG Platform — Multi-Tenant Retrieval-Augmented Generation as a Service

A production-oriented RAG backend built with **FastAPI** and **LangChain**, designed to be dropped into a real SaaS product: multiple clients (tenants) can each upload their own documents and query them through an isolated, rate-limited API, with async ingestion, pluggable chunking strategies, pluggable vector stores, caching, and MLOps observability baked in from the start.

This isn't a notebook-style RAG demo — it's structured the way a small team would actually ship a RAG feature to production: tenant isolation, background processing, structured logging, metrics, health checks, CI, and Docker Compose for the full stack.

## Why this exists

Most RAG tutorials show a single script that loads a PDF, embeds it, and answers one question. That's fine for learning the concept, but it skips everything that makes RAG hard to run as an actual product:

- **Multiple customers' data must never mix** — solved here with per-request tenant filtering at the vector-store query level, not application-level post-filtering.
- **Ingesting a large document shouldn't block an API request** — solved with a Celery-based background pipeline.
- **The same question gets asked repeatedly** — solved with a Redis cache in front of the LLM call.
- **You need to know when retrieval quality drops, not just when the server is up** — solved with Prometheus metrics on cache hit rate, chunk counts, and per-tenant latency.
- **Chunking one way is wrong for every document type** — solved with three interchangeable strategies (recursive, semantic, fixed) selectable per request.

## Architecture

```
                    ┌─────────────┐
   Client (Tenant)  │   FastAPI   │  /api/v1/documents/ingest  → enqueue
   X-API-Key  ─────▶│   (app/)    │  /api/v1/query             → sync RAG
                    └──────┬──────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
         ┌────────┐  ┌──────────┐  ┌───────────┐
         │Postgres│  │  Redis   │  │  Celery   │
         │ tenants│  │ cache +  │  │  worker   │
         │  docs  │  │  queue   │  │ (ingest)  │
         └────────┘  └──────────┘  └─────┬─────┘
                                          ▼
                                   ┌─────────────┐
                                   │ Qdrant /    │
                                   │ Chroma      │
                                   │ (vectors)   │
                                   └─────────────┘

         /metrics ──▶ Prometheus ──▶ (Grafana of your choice)
```

**Ingestion flow:** client uploads a file → API validates & stores metadata in Postgres → job is pushed to Celery/Redis → worker chunks the text, embeds it, and upserts into the vector store, tagged with `tenant_id` → status becomes queryable via `GET /documents/{id}`.

**Query flow:** client sends a question → check Redis cache → if miss, retrieve top-k chunks filtered by `tenant_id` → optional cross-encoder rerank for precision → build a grounded prompt → call the LLM → cache and return the answer with cited sources.

## Feature checklist

| Area | What's implemented |
|---|---|
| **RAG core** | LangChain-based retrieval + generation, grounded prompting, source citation in every response |
| **Chunking** | Recursive, semantic (embedding-breakpoint), and fixed-window strategies, selectable per document |
| **Vector store** | Qdrant (default) or Chroma, swappable via one env var, tenant-isolated at query time |
| **Embeddings/LLM** | OpenAI or HuggingFace embeddings; OpenAI or Anthropic for generation — swap via config, no code changes |
| **Multi-tenancy** | Hashed API keys per tenant, all data and queries scoped by `tenant_id` |
| **Async ingestion** | Celery + Redis background workers, with retry-on-failure |
| **Caching** | Redis-backed query cache to cut LLM cost on repeated questions |
| **Rate limiting** | Per-tenant sliding-window limiter backed by Redis (safe across replicas) |
| **Reranking** | Optional cross-encoder rerank stage for retrieval precision |
| **Observability** | Structured JSON logs, Prometheus metrics (`/metrics`), `/health` and `/health/live` probes |
| **Testing** | Pytest unit + API tests, coverage gate in CI |
| **CI/CD** | GitHub Actions: lint (ruff), type-check (mypy), tests with coverage, Docker build |
| **Deployment** | Multi-stage Dockerfile (non-root user, healthcheck), full docker-compose stack |

## Tech stack

`FastAPI` · `LangChain` · `OpenAI / Anthropic` · `Qdrant` / `ChromaDB` · `PostgreSQL` (async SQLAlchemy) · `Redis` · `Celery` · `Prometheus` · `Docker` · `pytest` · `GitHub Actions`

## Getting started

### 1. Configure environment

```bash
cp .env.example .env
# then edit .env: set OPENAI_API_KEY, ADMIN_API_KEY, JWT_SECRET
```

### 2. Run the full stack

```bash
make up          # builds and starts api, worker, postgres, redis, qdrant, prometheus
make logs        # tail api + worker logs
```

The API is now live at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`.

### 3. Create a tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "X-Admin-Key: <your ADMIN_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name": "acme-corp", "plan": "pro"}'
```

Save the returned `api_key` — it's shown only once.

### 4. Ingest a document

```bash
curl -X POST http://localhost:8000/api/v1/documents/ingest \
  -H "X-API-Key: <tenant api_key>" \
  -F "file=@handbook.pdf" \
  -F "chunk_strategy=semantic"
```

### 5. Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: <tenant api_key>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the refund policy?", "top_k": 5}'
```

## Running locally without Docker

```bash
make install
# start postgres/redis/qdrant yourself, or point DATABASE_URL/REDIS_URL/QDRANT_URL
# at hosted instances (Supabase, Upstash, Qdrant Cloud all work)
make dev          # FastAPI with autoreload
make worker       # in a second terminal — Celery worker
```

## Testing

```bash
make test         # pytest with coverage report
make lint         # ruff
```

## Configuration reference

Every setting is an environment variable (see `.env.example`), including which vector backend, embedding provider, and LLM to use — switching from OpenAI to a self-hosted HuggingFace embedding model, or from Qdrant to Chroma for a smaller deployment, is a config change, not a code change.

## Extending this project

- **Add a new chunking strategy**: implement a function in `app/chunking.py` matching the `(text, chunk_size, chunk_overlap) -> list[Chunk]` signature and register it in `_STRATEGIES`.
- **Add a new vector backend**: extend `VectorStoreClient` in `app/vectorstore.py` with the same `upsert`/`search` interface.
- **Add a new LLM provider**: extend `get_llm()` in `app/rag_chain.py`.
- **Swap SQLite for local dev / Postgres for prod**: just change `DATABASE_URL` — SQLAlchemy handles the rest (see `tests/conftest.py` for the SQLite pattern used in CI).

## Known limitations / roadmap

This is a portfolio-grade reference implementation, not a battle-tested product — a few things a real production rollout would add next:

- Alembic migrations instead of `create_all` for schema changes without downtime
- Streaming responses (SSE) for the `/query` endpoint when `stream=true`
- Per-tenant usage billing hooks (tokens in/out, storage)
- JWT-based end-user auth layered on top of tenant API keys for multi-seat tenants

## License

MIT — see [LICENSE](LICENSE).
