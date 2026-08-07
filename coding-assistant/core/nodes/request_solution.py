"""
core.nodes.request_solution: hand a generated artifact to the user for
feedback.

Responsibility:
    Marks the turn as pending user feedback once an artifact has been
    produced, so the next incoming message is routed (via
    state.awaiting_feedback and core.router) to feedback handling instead
    of re-classification.

State fields read:
    - artifacts

State fields written (sole writer, per core/state.py):
    - awaiting_feedback

Allowed imports:
    - core.state, core.types

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - services.* (this node is pure bookkeeping — no I/O)
    - other core.nodes modules
"""
