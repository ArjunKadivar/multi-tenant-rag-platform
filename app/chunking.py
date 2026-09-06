"""
Chunking strategies.

Three interchangeable strategies are exposed behind one factory function so
callers (and the API) can pick whichever fits a given document type:

- `recursive`  : LangChain's RecursiveCharacterTextSplitter — good general
                 default, respects paragraph/sentence boundaries.
- `semantic`   : Splits on embedding-similarity breakpoints between sentences
                 so a chunk stays topically coherent even in dense prose.
- `fixed`      : Naive fixed-size windows with overlap — fastest, useful for
                 already-structured data (logs, transcripts).
"""
from dataclasses import dataclass

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker

from app.config import get_settings
from app.embeddings import get_embedding_client

settings = get_settings()


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict


def chunk_recursive(text: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(text)
    return [Chunk(text=p, index=i, metadata={"strategy": "recursive"}) for i, p in enumerate(pieces)]


def chunk_fixed(text: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    step = max(chunk_size - chunk_overlap, 1)
    pieces = [text[i : i + chunk_size] for i in range(0, len(text), step) if text[i : i + chunk_size].strip()]
    return [Chunk(text=p, index=i, metadata={"strategy": "fixed"}) for i, p in enumerate(pieces)]


def chunk_semantic(text: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Embedding-driven semantic chunking with a size-based fallback.

    Falls back to `chunk_recursive` if the embedding backend is unavailable
    (e.g. missing API key in a dev environment), so ingestion never hard-fails
    purely because of the smarter strategy.
    """
    try:
        embeddings = get_embedding_client()
        splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
        pieces = splitter.split_text(text)
        return [Chunk(text=p, index=i, metadata={"strategy": "semantic"}) for i, p in enumerate(pieces)]
    except Exception:
        return chunk_recursive(text, chunk_size, chunk_overlap)


_STRATEGIES = {
    "recursive": chunk_recursive,
    "fixed": chunk_fixed,
    "semantic": chunk_semantic,
}


def chunk_text(
    text: str,
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    strategy = strategy or settings.DEFAULT_CHUNK_STRATEGY
    chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP

    fn = _STRATEGIES.get(strategy)
    if fn is None:
        raise ValueError(f"Unknown chunk strategy: {strategy}")
    return fn(text, chunk_size, chunk_overlap)
