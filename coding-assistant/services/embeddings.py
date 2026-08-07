"""
services/embeddings.py: embedding model adapter.

Responsibility:
    Wraps whichever embedding model/provider is in use behind a single
    interface used by both ingestion/ (indexing time) and
    core.nodes.retrieve (query time), so both paths stay guaranteed to
    use the same embedding model/config.

Allowed imports:
    - stdlib
    - the chosen embedding provider SDK
    - config.settings (for embedding_model)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb
"""
