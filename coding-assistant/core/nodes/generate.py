"""
core.nodes.generate: produce a code answer for a "generate" intent turn.

Responsibility:
    Runs the generate prompt (prompts/generate.v1.md) using the graded,
    relevant chunks as context, and packages any resulting code into
    Artifacts via the artifacts service.

State fields read:
    - user_message
    - attached_code
    - language
    - relevant_chunks
    - recent_turns
    - summary
    - profile

State fields written (sole writer, per core/state.py):
    - answer
    - artifacts

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/generate.v1.md by name+version)
    - services.artifacts (to register generated code blocks by id)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""

from __future__ import annotations

from core.state import AssistantState
from services import artifacts, llm


def run(state: AssistantState) -> dict:
    """Generate code (and an explanation) for this turn's request.

    Args:
        state: reads user_message, attached_code, language,
            relevant_chunks, recent_turns, summary, profile.

    Returns:
        A dict with exactly the keys "answer" and "artifacts" — the two
        fields this node owns.

    Failure modes:
        Propagates whatever services.llm.run_generator raises, e.g.
        RuntimeError if no API key is configured.
    """
    answer, artifact_specs = llm.run_generator(
        state.user_message,
        state.attached_code,
        state.language,
        state.relevant_chunks,
        state.recent_turns,
        state.summary,
        state.profile,
    )
    generated = [
        artifacts.make_artifact(spec["language"], spec["code"], spec.get("description"))
        for spec in artifact_specs
    ]
    return {"answer": answer, "artifacts": generated}
