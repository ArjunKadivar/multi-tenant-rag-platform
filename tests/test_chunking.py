from app.chunking import chunk_fixed, chunk_recursive, chunk_text

SAMPLE_TEXT = (
    "Retrieval-Augmented Generation combines a retriever with a generator. "
    "The retriever fetches relevant chunks from a vector store. "
    "The generator then conditions its answer on that retrieved context. "
) * 20  # long enough to force multiple chunks


def test_chunk_recursive_respects_size_bounds():
    chunks = chunk_recursive(SAMPLE_TEXT, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    # RecursiveCharacterTextSplitter can slightly exceed chunk_size at
    # separator boundaries; assert it's in the right ballpark, not exact.
    assert all(len(c.text) <= 260 for c in chunks)


def test_chunk_fixed_produces_overlapping_windows():
    chunks = chunk_fixed(SAMPLE_TEXT, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert chunks[0].text[-20:] in chunks[1].text[:40]  # overlap present


def test_chunk_text_dispatches_to_correct_strategy():
    chunks = chunk_text(SAMPLE_TEXT, strategy="fixed", chunk_size=150, chunk_overlap=10)
    assert all(c.metadata["strategy"] == "fixed" for c in chunks)


def test_chunk_text_rejects_unknown_strategy():
    import pytest

    with pytest.raises(ValueError):
        chunk_text(SAMPLE_TEXT, strategy="not-a-real-strategy")


def test_empty_text_produces_no_chunks():
    assert chunk_recursive("", chunk_size=100, chunk_overlap=10) == []
