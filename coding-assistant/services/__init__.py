"""
services: the boundary layer to the outside world.

Responsibility:
    Adapts vendor SDKs (LLM providers, Chroma, SQLite, sandboxed code
    runners) to the narrow, vendor-free interfaces and types that
    core/ depends on (see core/types.py). This is the only layer allowed
    to import third-party/vendor SDKs.

Allowed imports:
    - stdlib
    - third-party/vendor SDKs (chromadb, LLM provider SDKs, etc.)
    - core.types (to convert vendor objects into vendor-free dataclasses)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.* (dependency
      direction is app/ and api/ -> core/ -> services/; services/ never
      depends back on core/ beyond core.types)
    - streamlit, fastapi (services/ is UI/transport-agnostic)
"""
