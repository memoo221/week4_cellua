"""
core.nodes.explain: answer an "explain" intent turn.

Responsibility:
    Runs the explain prompt (prompts/explain.v1.md) to produce a
    natural-language answer for turns classified as explanation requests
    (no retrieval/generation loop involved).

State fields read:
    - user_message
    - attached_code
    - language
    - recent_turns
    - summary
    - profile

State fields written (sole writer, per core/state.py):
    - answer

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/explain.v1.md by name+version)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import llm


def run(state: AssistantState) -> dict:
    """Produce a natural-language answer for an "explain" intent turn.

    Args:
        state: reads user_message, attached_code, language, recent_turns,
            summary, profile.

    Returns:
        A dict with exactly the key "answer" — the one field this node
        owns.

    Failure modes:
        Propagates whatever services.llm.run_explainer raises, e.g.
        RuntimeError if no API key is configured.
    """
    answer = llm.run_explainer(
        state.user_message,
        state.attached_code,
        state.language,
        state.recent_turns,
        state.summary,
        state.profile,
    )
    return {"answer": answer}
