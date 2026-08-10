"""
services/runner/terminal_runner.py: run an Artifact's code as a local subprocess.

Responsibility:
    The simplest CodeRunner (see protocol.py): writes an Artifact's
    code to a temp file and executes it directly on the host via
    subprocess, under a wall-clock timeout. No sandboxing — this trusts
    the caller to only run code the user has already reviewed; it must
    not be exposed to untrusted/multi-tenant use without a real sandbox
    (see the deferred docker_runner.py in services/runner/__init__.py's
    docstring).

Allowed imports:
    - stdlib (subprocess, sys, tempfile, pathlib)
    - core.types (Artifact, ExecutionResult)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from core.types import Artifact, ExecutionResult

# Language -> (interpreter command, file suffix). Only languages listed
# here can actually be run; anything else is a ValueError from run().
_LANGUAGE_COMMANDS: dict[str, list[str]] = {
    "python": [sys.executable],
}
_LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python": ".py",
}


def supports(language: str) -> bool:
    """Whether run() can execute this language."""
    return language in _LANGUAGE_COMMANDS


def run(artifact: Artifact, timeout: float = 10.0) -> ExecutionResult:
    """Execute an Artifact's code as a local subprocess.

    Args:
        artifact: the code to run. artifact.language must be a key in
            _LANGUAGE_COMMANDS.
        timeout: wall-clock seconds before the process is killed.

    Returns:
        stdout/stderr captured from the run, its exit code, and whether
        it was killed for exceeding `timeout` (exit_code is -1 in that
        case — the process never returned one).

    Failure modes:
        ValueError if artifact.language isn't supported (check with
        supports() first rather than relying on this to signal it).
        OSError if the interpreter can't be launched or the temp file
        can't be created.
    """
    if not supports(artifact.language):
        raise ValueError(f"no runner configured for language {artifact.language!r}")

    suffix = _LANGUAGE_EXTENSIONS[artifact.language]
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as handle:
        handle.write(artifact.code)
        path = Path(handle.name)

    try:
        command = _LANGUAGE_COMMANDS[artifact.language] + [str(path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            return ExecutionResult(
                stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode, timed_out=False
            )
        except subprocess.TimeoutExpired as error:
            return ExecutionResult(
                stdout=error.stdout or "", stderr=error.stderr or "", exit_code=-1, timed_out=True
            )
    finally:
        path.unlink(missing_ok=True)
