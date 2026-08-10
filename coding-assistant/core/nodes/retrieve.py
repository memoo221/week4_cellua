"""
core.nodes.retrieve: fetch candidate context chunks for a "generate" turn.

Responsibility:
    Embeds the user's query and fetches the top-k candidate chunks from
    the vector store, ahead of grading.

State fields read:
    - user_message
    - attached_code
    - language

State fields written (sole writer, per core/state.py):
    - retrieved_chunks
    - retry_count (incremented on each attempt — see core/state.py's
      docstring on why this node owns the increment rather than
      core.router, which must stay pure)

Allowed imports:
    - core.state, core.types
    - services.embeddings, services.vectorstore

Must NOT import:
    - streamlit, fastapi, chromadb directly (only via services.vectorstore)
    - any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import embeddings, vectorstore


def run(state: AssistantState) -> dict:
    """Retrieve candidate chunks relevant to this turn's request.

    Embeds `user_message` (plus `attached_code`, if present, so a
    pasted snippet's own content shapes what gets retrieved alongside
    the question about it) and queries the vector store for the
    configured top_k nearest chunks.

    Args:
        state: reads user_message, attached_code, language, retry_count.

    Returns:
        A dict with exactly the keys "retrieved_chunks" and
        "retry_count" — the fields this node owns. retry_count is
        incremented every call, so core.router can bound how many
        times the retrieve/grade loop retries before giving up (see
        core.router.MAX_RETRIES, core.nodes.ask_for_help).

    Failure modes:
        RuntimeError if no embeddings API key is configured.
        requests.RequestException on a network/HTTP failure.
        chromadb errors on a query failure.
    """
    query_text = state.user_message
    if state.attached_code:
        query_text = f"{query_text}\n\n{state.attached_code}"
    query_embedding = embeddings.embed_query(query_text)
    return {"retrieved_chunks": vectorstore.query(query_embedding), "retry_count": state.retry_count + 1}
