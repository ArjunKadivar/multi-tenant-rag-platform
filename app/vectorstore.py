"""
Vector store abstraction.

Tenant isolation strategy: rather than one collection per tenant (which
doesn't scale past a few thousand tenants), every vector carries a
`tenant_id` payload field and every query is filtered on it. This keeps a
single collection per environment while guaranteeing tenants never see each
other's data — the filter is applied server-side by the vector DB, not
after retrieval.
"""
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.embeddings import get_embedding_client

COLLECTION_NAME = "rag_documents"
VECTOR_SIZE = 1536  # matches text-embedding-3-small; update if you swap models


class VectorStoreClient:
    def __init__(self):
        self.settings = get_settings()
        self.embeddings = get_embedding_client()
        self._backend = self._init_backend()

    def _init_backend(self):
        if self.settings.VECTOR_BACKEND == "qdrant":
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            client = QdrantClient(url=self.settings.QDRANT_URL)
            existing = [c.name for c in client.get_collections().collections]
            if COLLECTION_NAME not in existing:
                client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
            return client

        if self.settings.VECTOR_BACKEND == "chroma":
            import chromadb

            client = chromadb.PersistentClient(path=self.settings.CHROMA_PERSIST_DIR)
            return client.get_or_create_collection(COLLECTION_NAME)

        raise ValueError(f"Unsupported vector backend: {self.settings.VECTOR_BACKEND}")

    def upsert(self, tenant_id: str, document_id: str, chunks: list[str], metadatas: list[dict]) -> int:
        vectors = self.embeddings.embed_documents(chunks)
        ids = [f"{document_id}:{i}" for i in range(len(chunks))]
        payloads = [{**m, "tenant_id": tenant_id, "document_id": document_id, "text": c} for m, c in zip(metadatas, chunks)]

        if self.settings.VECTOR_BACKEND == "qdrant":
            from qdrant_client.models import PointStruct
            import hashlib

            points = [
                PointStruct(id=int(hashlib.sha1(pid.encode()).hexdigest()[:15], 16), vector=vec, payload=payload)
                for pid, vec, payload in zip(ids, vectors, payloads)
            ]
            self._backend.upsert(collection_name=COLLECTION_NAME, points=points)
        else:  # chroma
            self._backend.add(ids=ids, embeddings=vectors, metadatas=payloads, documents=chunks)

        return len(chunks)

    def search(self, tenant_id: str, query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
        query_vector = self.embeddings.embed_query(query)

        if self.settings.VECTOR_BACKEND == "qdrant":
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            conditions = [FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
            for k, v in (filters or {}).items():
                conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))

            hits = self._backend.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=Filter(must=conditions),
                limit=top_k,
            )
            return [{"score": h.score, **h.payload} for h in hits]

        # chroma
        where = {"tenant_id": tenant_id, **(filters or {})}
        results = self._backend.query(query_embeddings=[query_vector], n_results=top_k, where=where)
        out = []
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            out.append({"score": 1 - dist, "text": doc, **meta})
        return out


@lru_cache
def get_vector_store() -> VectorStoreClient:
    return VectorStoreClient()
