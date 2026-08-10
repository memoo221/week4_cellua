"""
core.nodes.learn_taught_fact: persist a user-supplied correction into the
vector store.

Responsibility:
    Runs on the turn immediately after core.nodes.ask_for_help asked the
    user to supply a correct solution or reference. Embeds the user's
    reply — paired with the original question that failed retrieval —
    and upserts it into the vector store, so future retrieval for
    similar questions can find it. This is the "human feedback
    learning" loop: what the assistant doesn't know today, it can be
    taught, and it'll know tomorrow (in any future conversation, not
    just this one — the taught fact lands in the same index
    core.nodes.retrieve queries).

State fields read:
    - user_message (the taught answer)
    - pending_question (the original question that failed retrieval,
      set by core.nodes.ask_for_help)

State fields written (sole writer, per core/state.py):
    - answer
    - awaiting_teaching (cleared back to False)
    - pending_question (cleared back to None)

Allowed imports:
    - core.state, core.types
    - services.embeddings, services.vectorstore (to store the taught fact)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

import hashlib

from core.state import AssistantState
from core.types import Chunk
from services import embeddings, vectorstore

_THANKS_MESSAGE = "Thanks — I've learned that and will use it for similar questions in the future."


def run(state: AssistantState) -> dict:
    """Store the user's taught correction as a retrievable Chunk.

    Args:
        state: reads user_message (the taught answer) and
            pending_question (what was originally asked).

    Returns:
        A dict with exactly the keys "answer", "awaiting_teaching", and
        "pending_question" — the fields this node owns.

    Failure modes:
        RuntimeError if no embeddings API key is configured.
        requests.RequestException on a network/HTTP failure.
        chromadb errors on a write failure.
    """
    text = f"Q: {state.pending_question}\nA (taught by user): {state.user_message}"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    chunk = Chunk(
        id=f"taught-{digest}", text=text, source="taught-by-user", score=0.0, metadata={"symbol": "user_taught"}
    )

    vector = embeddings.embed_batch([text])[0]
    vectorstore.upsert([chunk], [vector])

    return {"answer": _THANKS_MESSAGE, "awaiting_teaching": False, "pending_question": None}
