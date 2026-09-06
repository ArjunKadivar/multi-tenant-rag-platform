"""
Prometheus metrics — scraped at /metrics. This is the MLOps observability
surface: request volume/latency per tenant, cache hit rate, ingestion
throughput, and retrieval quality proxies (chunk counts returned).
"""
from prometheus_client import Counter, Histogram

QUERY_COUNT = Counter("rag_queries_total", "Total RAG queries", ["tenant_id", "cached"])
QUERY_LATENCY = Histogram("rag_query_latency_seconds", "End-to-end query latency", ["tenant_id"])
INGESTION_COUNT = Counter("rag_documents_ingested_total", "Documents ingested", ["tenant_id", "status"])
CHUNKS_CREATED = Counter("rag_chunks_created_total", "Chunks created during ingestion", ["tenant_id", "strategy"])
LLM_ERRORS = Counter("rag_llm_errors_total", "LLM call failures", ["provider"])
