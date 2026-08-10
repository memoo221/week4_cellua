"""
services/vectorstore.py: Chroma behind a narrow interface.

Responsibility:
    The only file in the project allowed to import chromadb. Exposes a
    narrow query/upsert interface in terms of core.types.Chunk, converting
    Chroma's native result objects at the boundary so no vendor type ever
    reaches core.nodes.retrieve or ingestion/build_index.py.

Allowed imports:
    - stdlib
    - chromadb
    - core.types (Chunk)
    - config.settings (chroma_path, collection_name, top_k, rerank_top_n)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, any LLM SDK
"""

from __future__ import annotations

import chromadb

from config.settings import get_settings
from core.types import Chunk


def _collection() -> chromadb.Collection:
    """Open (creating if needed) the configured Chroma collection.

    Returns:
        A handle to the on-disk collection at config.settings.chroma_path,
        named config.settings.collection_name.

    Failure modes:
        chromadb errors if chroma_path is unwritable.
    """
    settings = get_settings()
    client = chromadb.PersistentClient(path=settings.chroma_path)
    return client.get_or_create_collection(settings.collection_name)


def upsert(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    """Insert or update chunks in the vector store.

    Args:
        chunks: the chunks to store, produced by ingestion/chunker.py.
            Each chunk's `id` is used as Chroma's document id, so
            re-ingesting a chunk with the same id overwrites it rather
            than duplicating it.
        embeddings: one vector per chunk, in the same order, from
            services.embeddings.embed_batch.

    Failure modes:
        ValueError if len(chunks) != len(embeddings).
        chromadb errors on a write failure.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(f"got {len(chunks)} chunks but {len(embeddings)} embeddings")
    if not chunks:
        return
    _collection().upsert(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[{"source": c.source, **c.metadata} for c in chunks],
    )


def query(embedding: list[float], top_k: int | None = None) -> list[Chunk]:
    """Fetch the top_k chunks nearest to a query embedding.

    Args:
        embedding: the query vector, from services.embeddings.embed_query.
        top_k: how many candidates to return; defaults to
            config.settings.top_k.

    Returns:
        Up to top_k Chunks, ordered nearest-first. `score` is Chroma's
        reported distance for that match (lower means more similar,
        given Chroma's default cosine/L2 distance space) — callers doing
        further ranking should treat it as relative, not absolute.

    Failure modes:
        chromadb errors on a query failure.
    """
    k = top_k if top_k is not None else get_settings().top_k
    result = _collection().query(query_embeddings=[embedding], n_results=k)

    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    chunks = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = dict(metadata)
        source = metadata.pop("source", "")
        chunks.append(Chunk(id=chunk_id, text=text, source=source, score=distance, metadata=metadata))
    return chunks
