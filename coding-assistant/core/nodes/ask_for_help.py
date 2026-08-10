"""
core.nodes.ask_for_help: ask the user for help instead of hallucinating.

Responsibility:
    Runs once retrieval/grading has been retried the allowed number of
    times (see core.router.MAX_RETRIES) and still hasn't found relevant
    context. Rather than let core.nodes.generate answer from
    context that was never actually relevant — a near-guaranteed
    hallucination — this node asks the user to supply the correct
    solution or reference directly, and flags the turn so the *next*
    incoming message is treated as that answer (see
    core.nodes.learn_taught_fact) instead of a fresh request.

State fields read:
    - user_message

State fields written (sole writer, per core/state.py):
    - answer
    - awaiting_teaching
    - pending_question

Allowed imports:
    - core.state, core.types

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - services.* (this node is pure bookkeeping — no I/O)
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState

_MESSAGE = (
    "I couldn't find relevant knowledge for your request. Could you provide "
    "the correct solution or reference so I can learn it for future interactions?"
)


def run(state: AssistantState) -> dict:
    """Ask the user for the correct answer instead of guessing.

    Args:
        state: reads user_message — kept as pending_question so
            core.nodes.learn_taught_fact can store the taught answer
            alongside the question that failed retrieval.

    Returns:
        A dict with exactly the keys "answer", "awaiting_teaching", and
        "pending_question" — the fields this node owns.

    Failure modes:
        None — pure, side-effect-free.
    """
    return {
        "answer": _MESSAGE,
        "awaiting_teaching": True,
        "pending_question": state.user_message,
    }
