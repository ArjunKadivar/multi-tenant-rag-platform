"""
The actual RAG pipeline: retrieve -> (optionally) rerank -> generate.

Kept as plain async functions rather than a hidden LCEL graph so it's easy
to unit test each stage (retrieval, reranking, generation) independently,
and easy to swap the LLM provider via config without touching this file.
"""
import time
from functools import lru_cache

from app.config import get_settings
from app.vectorstore import get_vector_store

PROMPT_TEMPLATE = """You are a precise assistant answering questions using ONLY the provided context.
If the context does not contain the answer, say you don't have enough information — never guess.

Context:
{context}

Question: {question}

Answer:"""


@lru_cache
def get_llm():
    settings = get_settings()
    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.LLM_MODEL, api_key=settings.OPENAI_API_KEY, temperature=0.1)
    if settings.LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.LLM_MODEL, api_key=settings.ANTHROPIC_API_KEY, temperature=0.1)
    raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


def _rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    """Cross-encoder rerank for precision above what cosine similarity alone gives.

    Lazily imports sentence-transformers so environments that disable
    reranking (RERANK_ENABLED=false) don't pay the model-load cost.
    """
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [(query, h["text"]) for h in hits]
        scores = model.predict(pairs)
        ranked = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
        return [h for h, _ in ranked[:top_k]]
    except Exception:
        return hits[:top_k]


async def answer_query(tenant_id: str, query: str, top_k: int | None, filters: dict) -> dict:
    settings = get_settings()
    top_k = top_k or settings.DEFAULT_TOP_K
    start = time.perf_counter()

    store = get_vector_store()
    # Over-fetch before reranking so the reranker has something to work with.
    fetch_k = top_k * 3 if settings.RERANK_ENABLED else top_k
    hits = store.search(tenant_id=tenant_id, query=query, top_k=fetch_k, filters=filters)

    if settings.RERANK_ENABLED and hits:
        hits = _rerank(query, hits, top_k)
    else:
        hits = hits[:top_k]

    if not hits:
        return {
            "answer": "I don't have any indexed documents matching this query.",
            "sources": [],
            "latency_ms": (time.perf_counter() - start) * 1000,
        }

    context = "\n\n---\n\n".join(h["text"] for h in hits)
    prompt = PROMPT_TEMPLATE.format(context=context, question=query)

    llm = get_llm()
    response = await llm.ainvoke(prompt)
    answer_text = response.content if hasattr(response, "content") else str(response)

    sources = [
        {
            "document_id": h.get("document_id", "unknown"),
            "source_name": h.get("source_name", h.get("document_id", "unknown")),
            "chunk_text": h["text"][:400],
            "score": float(h.get("score", 0.0)),
        }
        for h in hits
    ]

    return {
        "answer": answer_text,
        "sources": sources,
        "latency_ms": (time.perf_counter() - start) * 1000,
    }
