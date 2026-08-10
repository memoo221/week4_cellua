"""
ingestion/build_index.py: CLI entrypoint wiring load -> chunk -> embed -> upsert.

Responsibility:
    The one place that composes ingestion/loader.py and
    ingestion/chunker.py with the embeddings/vectorstore adapters to
    actually populate the vector store. Run out-of-band from a live
    request — never imported by core/.

    Usage:
      `python -m ingestion.build_index`        indexes the HumanEval
                                                corpus (the project's
                                                chosen RAG dataset — see
                                                ingestion/loader.py:
                                                iter_humaneval_documents).
      `python -m ingestion.build_index PATH`   indexes a local directory
                                                instead, via
                                                ingestion.loader.iter_documents.

Allowed imports:
    - stdlib
    - ingestion.loader, ingestion.chunker
    - services.embeddings, services.vectorstore

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi
"""

from __future__ import annotations

import sys
from typing import Iterable

from ingestion.chunker import chunk_document
from ingestion.loader import Document, iter_documents, iter_humaneval_documents
from services import embeddings, vectorstore

# Batch size for embed+upsert calls — bounds how many chunks (and how
# large a request body) are in flight at once, independent of
# services.embeddings' own per-HTTP-request batch cap.
_UPSERT_BATCH_SIZE = 64


def build_index(documents: Iterable[Document]) -> int:
    """Chunk every document and upsert the results into Chroma.

    Args:
        documents: Documents to ingest, from either
            ingestion.loader.iter_documents or
            ingestion.loader.iter_humaneval_documents.

    Returns:
        The total number of chunks upserted.

    Failure modes:
        RuntimeError if JINA_API_KEY isn't configured.
        requests.RequestException on a network/HTTP failure (fetching
        HumanEval, or calling the embeddings API).
        chromadb errors on a write failure.
    """
    batch = []
    total = 0
    for doc in documents:
        batch.extend(chunk_document(doc))
        while len(batch) >= _UPSERT_BATCH_SIZE:
            total += _upsert_batch(batch[:_UPSERT_BATCH_SIZE])
            batch = batch[_UPSERT_BATCH_SIZE:]
    if batch:
        total += _upsert_batch(batch)
    return total


def _upsert_batch(chunks: list) -> int:
    vectors = embeddings.embed_batch([c.text for c in chunks])
    vectorstore.upsert(chunks, vectors)
    return len(chunks)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        label = sys.argv[1]
        count = build_index(iter_documents(sys.argv[1]))
    else:
        label = "HumanEval"
        count = build_index(iter_humaneval_documents())
    print(f"Indexed {count} chunks from {label}")
