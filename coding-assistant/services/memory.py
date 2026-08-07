"""
services/memory.py: SQLite-backed memory — buffer, summary, profile.

Responsibility:
    Owns the three memory tiers for a thread: the raw recent-message
    buffer, a rolling text summary of older turns, and a durable
    cross-thread user profile. The only file allowed to touch SQLite
    for these tiers. core.nodes.load_memory reads through this module at
    the start of every turn; core.nodes.learn (once implemented) writes
    through it at the end.

Allowed imports:
    - stdlib (including sqlite3)
    - core.types (Turn — the shape load_buffer converts SQLite rows into)
    - config.settings

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config.settings import get_settings
from core.types import Turn

# How many of the most recent turns load_buffer returns. Older turns are
# expected to have been folded into the summary tier by learn, not kept
# in the buffer indefinitely.
BUFFER_SIZE = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_thread ON turns (thread_id, timestamp);

CREATE TABLE IF NOT EXISTS summaries (
    thread_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_facts (
    user_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);
"""


def _connect() -> sqlite3.Connection:
    """Open a connection to the memory DB, creating the schema if needed.

    Returns:
        A sqlite3.Connection with the turns/summaries/profile_facts
        tables guaranteed to exist.

    Failure modes:
        sqlite3.Error if the DB file/path is inaccessible.
    """
    db_path = get_settings().memory_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def load_buffer(thread_id: str) -> list[Turn]:
    """Fetch the most recent raw turns for a thread from the buffer tier.

    Args:
        thread_id: identifies which conversation's buffer to read.

    Returns:
        Up to BUFFER_SIZE most recent turns, oldest first.

    Failure modes:
        sqlite3.Error if the underlying query fails.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, timestamp FROM turns
            WHERE thread_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (thread_id, BUFFER_SIZE),
        ).fetchall()
    return [Turn(role=role, content=content, timestamp=ts) for role, content, ts in reversed(rows)]


def load_summary(thread_id: str) -> str | None:
    """Fetch the rolling summary of turns older than the buffer.

    Args:
        thread_id: identifies which conversation's summary to read.

    Returns:
        The summary text, or None if none exists yet for this thread.

    Failure modes:
        sqlite3.Error if the underlying query fails.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT summary FROM summaries WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    return row[0] if row else None


def load_profile(user_id: str) -> dict[str, str]:
    """Fetch durable, cross-thread user profile facts.

    Args:
        user_id: identifies which user's profile to read. Deliberately
            not thread_id — profile facts must survive across separate
            conversations for the same person.

    Returns:
        Profile facts as a flat dict, or {} if none exist yet.

    Failure modes:
        sqlite3.Error if the underlying query fails.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value FROM profile_facts WHERE user_id = ?", (user_id,)
        ).fetchall()
    return dict(rows)


def save_turn(thread_id: str, turn: Turn) -> None:
    """Append one turn to a thread's buffer.

    Args:
        thread_id: which conversation this turn belongs to.
        turn: the role/content/timestamp to persist.

    Failure modes:
        sqlite3.Error if the write fails.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO turns (thread_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (thread_id, turn.role, turn.content, turn.timestamp),
        )


def save_summary(thread_id: str, summary: str) -> None:
    """Replace a thread's rolling summary.

    Args:
        thread_id: which conversation's summary to update.
        summary: the new summary text, replacing any prior value.

    Failure modes:
        sqlite3.Error if the write fails.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO summaries (thread_id, summary) VALUES (?, ?) "
            "ON CONFLICT(thread_id) DO UPDATE SET summary = excluded.summary",
            (thread_id, summary),
        )


def save_profile(user_id: str, facts: dict[str, str]) -> None:
    """Merge new facts into a user's profile (existing keys are overwritten).

    Args:
        user_id: which user's profile to update.
        facts: key/value pairs to upsert; keys not present are left alone.

    Failure modes:
        sqlite3.Error if the write fails.
    """
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO profile_facts (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            [(user_id, key, value) for key, value in facts.items()],
        )
