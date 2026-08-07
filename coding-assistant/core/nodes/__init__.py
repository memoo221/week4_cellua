"""
core.nodes: individual graph nodes.

Responsibility:
    Each module in this package defines one node function with signature
    `(state: AssistantState) -> dict`, returning only the state fields it
    writes (see core/state.py for the single-writer-per-field mapping).
    Nodes never call each other — sequencing lives in core/graph.py, and
    branching decisions live in core/router.py.

Allowed imports:
    - stdlib
    - core.state, core.types
    - services.* interfaces (nodes are where core/ is allowed to reach
      into services/, since app/ and api/ -> core/ -> services/)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly (go through the
      relevant services/ adapter instead)
    - other core.nodes modules (no node-to-node calls)
"""
