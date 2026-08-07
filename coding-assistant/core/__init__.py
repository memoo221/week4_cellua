"""
core: the framework-agnostic heart of the assistant.

Responsibility:
    Houses the state contract (state.py), vendor-free types (types.py),
    the pure routing policy (router.py), the node implementations
    (nodes/), and the graph wiring (graph.py).

Allowed imports:
    - stdlib
    - core.* (submodules of this package)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - anything from services/, app/, api/

    core/ is the layer everything else depends on (app/ and api/ -> core/
    -> services/). It must remain importable with zero third-party
    dependencies installed.
"""
