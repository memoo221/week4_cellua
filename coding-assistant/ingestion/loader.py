"""
ingestion/loader.py: read source documents into raw text.

Responsibility:
    Produce raw Document objects for ingestion/chunker.py to split next,
    from either of two sources:
      - iter_documents: walks a local directory (kept for pointing the
        pipeline at an arbitrary codebase later).
      - iter_humaneval_documents: the project's actual RAG corpus —
        fetches the openai/openai_humaneval dataset from HuggingFace's
        datasets-server (https://datasets-server.huggingface.co/rows),
        no local download or `datasets`/pyarrow dependency required.
        Each of its 164 problems' `prompt` + `canonical_solution`
        concatenates into one complete, parseable Python function, so
        it flows through the same ast-based chunking as any other .py
        source.
    `source` on the returned Document is whatever stable identifier
    downstream Chunks should carry — chunker.py and the vectorstore
    adapter never see a filesystem path or dataset row directly, only
    what this module hands them.

    Local text extraction is per file type: plain read for code/text/
    markdown (see _TEXT_EXTENSIONS); anything requiring a parser (PDF,
    notebooks, etc.) is deferred until a concrete corpus format needs
    it — this module skips (does not crash on) file types it doesn't
    yet know how to read, and silently skips files it can't decode as
    UTF-8 (binary files that slipped past the extension filter).

State fields read: none — ingestion never touches AssistantState.

Allowed imports:
    - stdlib only (pathlib, os, and format-specific stdlib modules)
    - requests (to fetch the HumanEval corpus — same HTTP client choice
      as services/llm.py and services/embeddings.py)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
    - services.* / the embeddings or vectorstore adapters (loader only
      produces raw text; ingestion/build_index.py is the one place that
      wires load -> chunk -> embed -> upsert together)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import requests

# File types this loader knows how to read as plain UTF-8 text. Extend as
# new corpus formats are decided (see module docstring); anything not
# listed here is skipped rather than guessed at.
_TEXT_EXTENSIONS = {".py", ".md", ".txt", ".rst"}

# Directories never worth walking into, regardless of what's inside them.
_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", "data"}

# The project's RAG corpus: HumanEval, served through HF's public
# datasets-server rows API (JSON, paginated) rather than the parquet
# export, so no `datasets`/pyarrow dependency is needed to read it.
_HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
_HUMANEVAL_DATASET = "openai/openai_humaneval"
_HUMANEVAL_CONFIG = "openai_humaneval"
_HUMANEVAL_SPLIT = "test"  # HumanEval's only split — all 164 problems.
_HF_PAGE_SIZE = 100


@dataclass
class Document:
    """One loaded file, ready for ingestion/chunker.py to split.

    Attributes:
        text: the file's raw text content.
        source: a stable identifier for this document — its path
            relative to the walked root, using forward slashes so it's
            the same on every OS.
    """

    text: str
    source: str


def iter_documents(root: str | Path) -> Iterator[Document]:
    """Walk `root` and yield a Document for every readable text file.

    Args:
        root: directory to walk recursively.

    Yields:
        One Document per file under `root` whose extension is in
        _TEXT_EXTENSIONS and whose content decodes as UTF-8, in
        os.walk's traversal order.

    Failure modes:
        FileNotFoundError / NotADirectoryError if `root` doesn't exist.
        Individual unreadable files are skipped, not raised — a single
        bad file must not abort an entire indexing run.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix not in _TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield Document(text=text, source=path.relative_to(root).as_posix())


def iter_humaneval_documents() -> Iterator[Document]:
    """Fetch the HumanEval dataset and yield one Document per problem.

    Each problem's `prompt` (imports, function signature, docstring)
    and `canonical_solution` (the reference implementation body) are
    concatenated into one complete function body — this is exactly how
    HumanEval's own evaluation harness reconstructs a runnable solution,
    so the result is valid Python that ingestion/chunker.py's ast-based
    path can chunk like any other source file. `source` is given a
    `.py` suffix for that reason, even though nothing was read from
    disk.

    Yields:
        One Document per HumanEval problem (164 total), in dataset
        order.

    Failure modes:
        requests.RequestException on a network/HTTP failure.
        KeyError if HuggingFace's response shape changes.
    """
    offset = 0
    while True:
        response = requests.get(
            _HF_ROWS_URL,
            params={
                "dataset": _HUMANEVAL_DATASET,
                "config": _HUMANEVAL_CONFIG,
                "split": _HUMANEVAL_SPLIT,
                "offset": offset,
                "length": _HF_PAGE_SIZE,
            },
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()["rows"]
        if not rows:
            return
        for entry in rows:
            row = entry["row"]
            text = row["prompt"] + row["canonical_solution"]
            source = f"humaneval/{row['task_id'].replace('/', '_')}.py"
            yield Document(text=text, source=source)
        offset += len(rows)
