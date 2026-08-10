"""
core.nodes.learn: persist feedback and memory updates for future turns.

Responsibility:
    Runs the summarize prompt (prompts/summarize.v1.md) and/or profile
    extraction over the completed turn, and persists the results via the
    memory service so that the *next* request's load_memory node picks
    them up. This node does not mutate state.summary or state.profile
    directly — those fields' sole writer is core.nodes.load_memory, at
    the start of the next request. learn.py only writes to persistent
    storage as a side effect through services.memory.

State fields read:
    - thread_id
    - user_id (to scope the durable profile — see services.memory.save_profile)
    - user_message
    - answer
    - artifacts
    - recent_turns

State fields written:
    - none (side effects only, via services.memory; may append to trace)

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/summarize.v1.md by name+version)
    - services.memory (to persist buffer/summary/profile updates)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.state import AssistantState
from core.types import Turn
from services import llm, memory


def run(state: AssistantState) -> dict:
    """Summarize this turn and persist it via the memory service.

    Reads the thread's current summary/profile straight from
    services.memory rather than state.summary/state.profile — those
    fields reflect the start of this turn and nothing else writes them
    mid-turn, but going through the same service learn persists through
    keeps this node's only source of truth for existing memory
    consistent with its only sink for new memory.

    Args:
        state: reads thread_id, user_id, user_message, answer,
            artifacts, recent_turns.

    Returns:
        An empty dict — this node writes no state fields, only
        persistent storage (see module docstring).

    Failure modes:
        Propagates whatever services.llm.run_summarizer or
        services.memory raise, e.g. RuntimeError if no API key is
        configured, or sqlite3.Error on a storage failure.
    """
    existing_summary = memory.load_summary(state.thread_id)
    existing_profile = memory.load_profile(state.user_id)

    new_summary, profile_updates = llm.run_summarizer(
        state.user_message, state.answer, state.artifacts, state.recent_turns, existing_summary, existing_profile
    )

    now = datetime.now(timezone.utc).isoformat()
    memory.save_turn(state.thread_id, Turn(role="user", content=state.user_message, timestamp=now))
    memory.save_turn(state.thread_id, Turn(role="assistant", content=state.answer or "", timestamp=now))
    memory.save_summary(state.thread_id, new_summary)
    if profile_updates:
        memory.save_profile(state.user_id, profile_updates)

    return {}
