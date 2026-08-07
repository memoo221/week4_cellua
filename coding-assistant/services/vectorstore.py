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
