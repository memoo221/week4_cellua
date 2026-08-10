"""
services/embeddings.py: Jina AI hosted embeddings adapter.

Responsibility:
    Wraps Jina AI's embeddings API behind a single interface used by both
    ingestion/build_index.py (indexing time) and core.nodes.retrieve
    (query time), so both paths stay guaranteed to use the same
    embedding model/config (see config.settings.embedding_model).

Allowed imports:
    - stdlib
    - requests (same HTTP client choice as services/llm.py)
    - config.settings (jina_api_key, jina_base_url, embedding_model)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb
"""

from __future__ import annotations

import requests

from config.settings import get_settings

# Jina's embeddings endpoint caps how many inputs one request may embed —
# batch_embed chunks its input list to this size rather than sending an
# unbounded request body.
_MAX_BATCH_SIZE = 100


def _embed(texts: list[str], task: str) -> list[list[float]]:
    """Call Jina AI's /embeddings endpoint for a batch of inputs.

    Args:
        texts: the strings to embed, in order.
        task: Jina's `task` parameter — asymmetric embedding models
            (like jina-embeddings-v2-base-code) produce different
            vectors depending on whether the input is a search query or
            a document being indexed, so query and document call sites
            must pass the matching task name.

    Returns:
        One embedding vector per input, in the same order as `texts`.

    Failure modes:
        RuntimeError if JINA_API_KEY isn't configured.
        requests.RequestException on a network/HTTP failure.
        KeyError/IndexError if the response body doesn't have the
        expected shape.
    """
    settings = get_settings()
    if not settings.jina_api_key:
        raise RuntimeError("JINA_API_KEY is not set; see .env.example")
    if not texts:
        return []

    vectors: list[list[float]] = []
    for start in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[start : start + _MAX_BATCH_SIZE]
        response = requests.post(
            f"{settings.jina_base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.jina_api_key}"},
            json={"model": settings.embedding_model, "task": task, "input": batch},
            timeout=60,
        )
        response.raise_for_status()
        # Jina returns results tagged with their input index but not
        # necessarily in order — sort before trusting positional alignment
        # with `batch`.
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors.extend(item["embedding"] for item in data)
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single query string at retrieval time.

    Args:
        text: the query text (e.g. state.user_message).

    Returns:
        The query's embedding vector.

    Failure modes:
        See _embed.
    """
    return _embed([text], task="retrieval.query")[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document chunks at indexing time.

    Args:
        texts: chunk texts to embed, in order (e.g. from
            ingestion/chunker.py).

    Returns:
        One embedding vector per input, in the same order as `texts`.

    Failure modes:
        See _embed.
    """
    return _embed(texts, task="retrieval.passage")
