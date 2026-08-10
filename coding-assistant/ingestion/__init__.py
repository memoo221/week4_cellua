"""
ingestion: offline pipeline that populates the vector store.

Responsibility:
    Everything needed to go from source documents on disk to embedded
    Chunks sitting in Chroma, run out-of-band from a live request (via
    build_index.py), never imported by the request-time graph in core/.

    Pipeline shape: loader.py reads raw (text, source) pairs from disk ->
    chunker.py splits each into retrieval-sized Chunks -> services under
    services/ (or wherever embeddings.py/vectorstore.py currently live)
    embed and upsert them. build_index.py is the thin CLI that wires
    those steps together.

Allowed imports:
    - stdlib
    - core.types (Chunk — the shape chunker.py produces)
    - the embedding/vectorstore adapters this pipeline upserts through

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.* (ingestion runs
      offline, never as part of a request's graph traversal)
    - streamlit, fastapi
"""
