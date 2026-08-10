"""
services/runner: execute generated code on demand.

Responsibility:
    Backends that take a core.types.Artifact and actually run it,
    returning a core.types.ExecutionResult. This is a UI-triggered
    action (a user clicking "run"), not part of the turn graph — no
    core.nodes module or AssistantState field represents code
    execution, so nothing under core/ imports this package.

    protocol.py defines the interface every backend implements;
    terminal_runner.py is the only implementation so far (a plain local
    subprocess, no sandboxing). A future docker_runner.py can implement
    the same interface with real isolation without callers changing.

Allowed imports:
    - stdlib
    - core.types (Artifact, ExecutionResult)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
"""
