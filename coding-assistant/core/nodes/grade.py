"""
core.nodes.grade: judge relevance of retrieved chunks before generation.

Responsibility:
    Runs the grade prompt (prompts/grade.v1.md) against each retrieved
    chunk, filters down to the relevant subset, and produces an overall
    grade that core.router uses to decide whether to proceed to generate
    or loop back to retrieve (bounded by retry_count).

State fields read:
    - user_message
    - retrieved_chunks

State fields written (sole writer, per core/state.py):
    - chunk_grades
    - relevant_chunks
    - overall_grade

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/grade.v1.md by name+version)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import llm


def run(state: AssistantState) -> dict:
    """Grade this turn's retrieved chunks for relevance.

    Args:
        state: reads user_message, retrieved_chunks.

    Returns:
        A dict with exactly the keys "chunk_grades", "relevant_chunks",
        and "overall_grade" — the three fields this node owns. When
        retrieved_chunks is empty, skips the LLM call entirely and
        grades as insufficient — there's nothing to judge.

    Failure modes:
        Propagates whatever services.llm.run_grader raises, e.g.
        RuntimeError if no API key is configured.
    """
    if not state.retrieved_chunks:
        return {"chunk_grades": {}, "relevant_chunks": [], "overall_grade": "insufficient"}

    chunk_grades, overall_grade = llm.run_grader(state.user_message, state.retrieved_chunks)
    relevant_chunks = [chunk for chunk in state.retrieved_chunks if chunk_grades.get(chunk.id) == "relevant"]
    return {"chunk_grades": chunk_grades, "relevant_chunks": relevant_chunks, "overall_grade": overall_grade}
