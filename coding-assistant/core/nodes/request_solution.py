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

from __future__ import annotations

from core.state import AssistantState


def run(state: AssistantState) -> dict:
    """Flag this turn's artifacts as awaiting the user's feedback.

    Args:
        state: reads artifacts.

    Returns:
        A dict with exactly the key "awaiting_feedback" — the one field
        this node owns. core.graph only calls this node when
        state.artifacts is non-empty, so this is True in practice, but
        it's derived from artifacts rather than hardcoded so the node
        stays correct if that calling convention ever changes.

    Failure modes:
        None — pure, side-effect-free.
    """
    return {"awaiting_feedback": bool(state.artifacts)}
