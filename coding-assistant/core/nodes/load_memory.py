"""
core.nodes.load_memory: hydrate a turn's state with prior conversation memory.

Responsibility:
    First node in the graph for a given request. Loads the buffer of
    recent turns, the rolling summary, and the long-lived user profile
    for `state.thread_id` from the memory service, and returns them as
    the initial state update.

State fields read:
    - thread_id
    - user_id

State fields written (sole writer, per core/state.py):
    - recent_turns
    - summary
    - profile

Allowed imports:
    - core.state, core.types
    - services.memory (the narrow interface this node depends on)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import memory


def run(state: AssistantState) -> dict:
    """Load recent_turns/summary (by thread_id) and profile (by user_id).

    Args:
        state: state.thread_id scopes recent_turns/summary; state.user_id
            scopes profile, so it survives across separate threads.

    Returns:
        A dict with exactly the keys "recent_turns", "summary", and
        "profile" — the three fields this node owns.

    Failure modes:
        Propagates whatever services.memory raises, e.g. sqlite3.Error on
        a storage failure.
    """
    return {
        "recent_turns": memory.load_buffer(state.thread_id),
        "summary": memory.load_summary(state.thread_id),
        "profile": memory.load_profile(state.user_id),
    }
