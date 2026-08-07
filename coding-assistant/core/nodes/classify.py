"""
core.nodes.classify: determine user intent and code language for this turn.

Responsibility:
    Runs the classifier prompt (prompts/classifier.v1.md) against the
    user's message (and attached code, if any) to decide what kind of
    turn this is, feeding core.router's branching decision.

State fields read:
    - user_message
    - attached_code
    - recent_turns
    - summary

State fields written (sole writer, per core/state.py):
    - intent
    - intent_confidence
    - language

Allowed imports:
    - core.state, core.types
    - services.llm (for the classifier call, referencing the prompt by
      name+version — never by inline prompt text)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import llm


def run(state: AssistantState) -> dict:
    """Classify this turn's intent, confidence, and code language.

    Args:
        state: reads user_message, attached_code, recent_turns, summary.

    Returns:
        A dict with exactly the keys "intent", "intent_confidence", and
        "language" — the three fields this node owns.

    Failure modes:
        Propagates whatever services.llm.run_classifier raises, e.g.
        NotImplementedError until an LLM provider is wired in.
    """
    intent, confidence, language = llm.run_classifier(
        state.user_message, state.attached_code, state.recent_turns, state.summary
    )
    return {"intent": intent, "intent_confidence": confidence, "language": language}
