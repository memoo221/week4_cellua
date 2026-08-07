"""
AssistantState: the single source of truth for one request's journey through
the graph.

Responsibility:
    Define the complete, typed schema that every node reads from and writes
    to. This is the contract that makes nodes composable without them
    knowing about each other.

Allowed imports:
    - stdlib only (dataclasses, typing)
    - core.types (plain vendor-free dataclasses)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - anything from services/, app/, api/

Rules encoded here:
    1. Every field has exactly one writer. The writer is documented in the
       comment above the field. Nodes must return a dict containing ONLY the
       fields they write — never the whole state.
    2. Nodes never call other nodes. They only read `state` and return a
       partial-update dict. core/graph.py is the only place that sequences
       nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.types import Artifact, Chunk, Turn


@dataclass
class AssistantState:
    """Full state passed through the graph for a single turn.

    Every node's signature is `(state: AssistantState) -> dict`, and the
    returned dict must only contain the keys the node is documented below
    as writing. See core/graph.py for how partial updates are merged back
    into the state between node calls.
    """

    # --- Request identity -------------------------------------------------
    # Writer: api/app entrypoint (set once, at request creation).
    request_id: str

    # Writer: api/app entrypoint (set once, at session/thread creation).
    thread_id: str

    # Writer: api/app entrypoint (set once, from the caller's identity —
    # e.g. an authenticated user id, or a stable local-user default before
    # auth exists). Scopes the durable `profile` tier across threads;
    # `thread_id` alone only scopes a single conversation's buffer/summary.
    user_id: str

    # --- Raw input -----------------------------------------------------
    # Writer: api/app entrypoint, from the user's submitted message.
    user_message: str

    # Writer: api/app entrypoint, from the user's attached code (if any).
    attached_code: str | None

    # Writer: core.nodes.classify (detected or user-declared code language).
    language: str | None

    # --- Memory ----------------------------------------------------------
    # Writer: core.nodes.load_memory. Recent raw turns from the buffer tier.
    recent_turns: list[Turn] = field(default_factory=list)

    # Writer: core.nodes.load_memory. Rolling summary of older turns.
    summary: str | None = None

    # Writer: core.nodes.load_memory. Long-lived user profile facts, keyed
    # by user_id (not thread_id) — persists across separate conversations.
    profile: dict[str, str] = field(default_factory=dict)

    # --- Intent classification -------------------------------------------
    # Writer: core.nodes.classify. One of a fixed set of intent labels
    # (e.g. "explain", "generate", "unknown").
    intent: str | None = None

    # Writer: core.nodes.classify. Confidence score in [0, 1] for `intent`.
    intent_confidence: float = 0.0

    # Writer: core.router (increments) — the only field the router itself
    # writes, used to bound generate/grade retry loops.
    retry_count: int = 0

    # --- Retrieval ---------------------------------------------------------
    # Writer: core.nodes.retrieve. Raw chunks returned from the vector store.
    retrieved_chunks: list[Chunk] = field(default_factory=list)

    # Writer: core.nodes.grade. Per-chunk relevance grades, keyed by chunk id.
    chunk_grades: dict[str, str] = field(default_factory=dict)

    # Writer: core.nodes.grade. Subset of retrieved_chunks judged relevant.
    relevant_chunks: list[Chunk] = field(default_factory=list)

    # Writer: core.nodes.grade. Aggregate grade for the retrieval as a whole
    # (e.g. "sufficient", "insufficient").
    overall_grade: str | None = None

    # --- Generation output ---------------------------------------------
    # Writer: core.nodes.explain OR core.nodes.generate (mutually exclusive
    # per turn, decided by the router).
    answer: str | None = None

    # Writer: core.nodes.generate. Code artifacts produced this turn.
    artifacts: list[Artifact] = field(default_factory=list)

    # --- Feedback loop -----------------------------------------------------
    # Writer: core.nodes.request_solution. True when the assistant is
    # waiting on the user to accept/reject/request changes to an artifact.
    awaiting_feedback: bool = False

    # --- Observability -----------------------------------------------------
    # Writer: every node appends its own trace entry (node name + metadata).
    # Each node only appends to this list; it never removes or overwrites
    # entries written by other nodes.
    trace: list[dict] = field(default_factory=list)
