"""
Vendor-free data contracts shared across core/, services/, app/, and api/.

Responsibility:
    Define plain dataclasses that represent domain concepts (a retrieved
    chunk, a generated code artifact, a code execution result, a
    conversation turn) without any dependency on the vendor SDKs that
    produce them (Chroma, an LLM provider, a sandbox runner, etc).
    Adapters in services/ are responsible for converting vendor-native
    objects into these types at the boundary — vendor types never escape
    services/.

Allowed imports:
    - stdlib only (dataclasses, typing)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - anything from services/, core/state.py, core/router.py, core/graph.py,
      app/, api/
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A single retrieved unit of context from the vector store.

    Produced by: services/vectorstore.py adapter, converting Chroma's
    native query results into this vendor-free shape.
    """

    id: str
    text: str
    source: str
    score: float
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Artifact:
    """A generated code block addressed by a stable id.

    Produced by: services/artifacts.py, wrapping model output emitted by
    core.nodes.generate.
    """

    id: str
    language: str
    code: str
    description: str | None = None


@dataclass
class ExecutionResult:
    """The outcome of running an Artifact through a CodeRunner.

    Produced by: services/runner/protocol.py implementations
    (docker_runner.py, terminal_runner.py).
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


@dataclass
class Turn:
    """A single prior exchange in a conversation, as recalled from memory.

    Produced by: services/memory.py, converting SQLite rows into this
    vendor-free shape for core.nodes.load_memory.
    """

    role: str
    content: str
    timestamp: str
