"""
services/runner/protocol.py: the interface every CodeRunner backend implements.

Responsibility:
    Defines the narrow shape callers (currently just app/) depend on, so
    a caller can swap terminal_runner.py for a future docker_runner.py
    without changing anything else.

Allowed imports:
    - stdlib (typing)
    - core.types (Artifact, ExecutionResult)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
"""

from __future__ import annotations

from typing import Protocol

from core.types import Artifact, ExecutionResult


class CodeRunner(Protocol):
    """Anything that can execute an Artifact and report the result."""

    def run(self, artifact: Artifact, timeout: float = 10.0) -> ExecutionResult:
        """Execute `artifact`'s code and capture the outcome.

        Args:
            artifact: the code to run.
            timeout: wall-clock seconds before the run is killed.

        Returns:
            stdout/stderr captured from the run, its exit code, and
            whether it was killed for exceeding `timeout`.
        """
        ...
