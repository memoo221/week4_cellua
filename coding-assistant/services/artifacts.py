"""
services/artifacts.py: wrap generated code blocks into addressable Artifacts.

Responsibility:
    Converts the raw {"language", "code", "description"} dicts that
    services/llm.py:run_generator parses out of the model's reply into
    core.types.Artifact objects, assigning each a stable id. The id is
    derived from the code's own content (a short hash), not a random
    uuid, so regenerating byte-identical code — e.g. a retry after an
    unrelated failure — doesn't manufacture a new identity for the same
    artifact.

Allowed imports:
    - stdlib (hashlib)
    - core.types (Artifact)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
"""

from __future__ import annotations

import hashlib

from core.types import Artifact


def make_artifact(language: str, code: str, description: str | None = None) -> Artifact:
    """Wrap one generated code block as an Artifact with a stable id.

    Args:
        language: lowercase language identifier (e.g. "python").
        code: the complete code for this block.
        description: one line on what this block is, if given.

    Returns:
        An Artifact whose id is a short hash of (language, code) — the
        same code in the same language always gets the same id.
    """
    digest = hashlib.sha256(f"{language}\0{code}".encode("utf-8")).hexdigest()[:12]
    return Artifact(id=f"artifact-{digest}", language=language, code=code, description=description)
