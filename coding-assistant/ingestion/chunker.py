"""
ingestion/chunker.py: split loaded documents into retrieval-sized chunks.

Responsibility:
    Take the Documents produced by ingestion/loader.py and split each
    into the core.types.Chunk pieces that get embedded and stored.

    Strategy: for .py sources, parse with ast and chunk at
    function/class boundaries so each chunk is a coherent unit (a
    docstring plus the code it documents, a whole small function, one
    method of a class) rather than an arbitrary slice. Boundaries are
    then adjusted against CHUNK_TOKEN_THRESHOLD, counted with tiktoken:
    a unit larger than the threshold is recursively split (a class into
    its methods; anything still oversized into line-packed pieces), and
    adjacent small siblings (e.g. a class's short methods, or a run of
    top-level imports/constants) are merged back together up to the
    threshold so the index isn't flooded with tiny, low-context chunks.
    Non-Python sources (.md, .txt, .rst) get the same threshold
    packing, split on paragraph boundaries instead of ast nodes.

    Each resulting Chunk's id is derived from its source path + line
    range, so re-ingesting an unchanged document upserts the same ids
    rather than duplicating them; a chunk's `symbol` (function/class/
    method name, or a merged join of several) is carried in metadata so
    retrieved context is citable back to real code, not just raw text.
    `score` is set to a placeholder 0.0 — score is a query-time property
    (similarity to a specific query), meaningless at index time, but
    Chunk has no default for it.

State fields read: none — ingestion never touches AssistantState.

Allowed imports:
    - stdlib (ast, dataclasses)
    - tiktoken (token counting, shared by the split/merge threshold)
    - core.types (Chunk)
    - ingestion.loader (Document — the input shape this module consumes)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb, any LLM SDK
    - services.* / the embeddings or vectorstore adapters (chunker only
      produces Chunks; ingestion/build_index.py is the one place that
      wires load -> chunk -> embed -> upsert together)
"""

from __future__ import annotations

import ast
import dataclasses
from functools import lru_cache

import tiktoken

from core.types import Chunk
from ingestion.loader import Document

# Target chunk size. Units larger than this get split further; adjacent
# units smaller than this get merged with their neighbors. Not exact —
# genuinely unsplittable single lines/statements may still exceed it.
CHUNK_TOKEN_THRESHOLD = 300

# Token counting isn't tied to any particular target model (Jina's
# tokenizer isn't public); cl100k_base is used purely as a consistent,
# reasonable proxy for "how big is this chunk" across the codebase.
_ENCODING_NAME = "cl100k_base"


@dataclasses.dataclass
class _Leaf:
    """One candidate chunk before the merge pass, with its token count
    cached so splitting/merging don't re-tokenize repeatedly."""

    symbol: str
    text: str
    start_line: int
    end_line: int
    tokens: int


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def _count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


def _make_leaf(symbol: str, text: str, start_line: int, end_line: int) -> _Leaf:
    return _Leaf(symbol=symbol, text=text, start_line=start_line, end_line=end_line, tokens=_count_tokens(text))


def chunk_document(doc: Document) -> list[Chunk]:
    """Split one loaded Document into retrieval-sized Chunks.

    Args:
        doc: a Document from ingestion/loader.py.

    Returns:
        Chunks covering the whole document, each within
        CHUNK_TOKEN_THRESHOLD tokens where the document's structure
        allows it, ordered as they appear in the source.

    Failure modes:
        None raised directly — a .py file that fails to parse falls
        back to the same paragraph-based splitting used for non-Python
        sources, rather than aborting the whole ingestion run.
    """
    if doc.source.endswith(".py"):
        leaves = _python_leaves(doc.text)
    else:
        leaves = _text_leaves(doc.text)
    leaves = _ensure_within_threshold(leaves)
    leaves = _merge_small(leaves)
    return [
        Chunk(
            id=f"{doc.source}::{leaf.start_line}-{leaf.end_line}",
            text=leaf.text,
            source=doc.source,
            score=0.0,
            metadata={
                "symbol": leaf.symbol,
                "start_line": str(leaf.start_line),
                "end_line": str(leaf.end_line),
            },
        )
        for leaf in leaves
    ]


# --- Python: ast-based boundaries -----------------------------------------


def _python_leaves(source: str) -> list[_Leaf]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _text_leaves(source)

    lines = source.splitlines()
    leaves: list[_Leaf] = []
    buffer_start: int | None = None

    def flush_buffer(end_line: int) -> None:
        nonlocal buffer_start
        if buffer_start is not None and end_line >= buffer_start:
            leaves.append(_make_leaf("<module>", "\n".join(lines[buffer_start - 1 : end_line]), buffer_start, end_line))
        buffer_start = None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            flush_buffer(_def_start(node) - 1)
            leaves.extend(_leaves_for_def(node, lines))
        elif buffer_start is None:
            buffer_start = node.lineno
    flush_buffer(len(lines))
    return leaves


def _def_start(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """First line of a def/class, including its decorators if any."""
    return node.decorator_list[0].lineno if node.decorator_list else node.lineno


def _leaves_for_def(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, lines: list[str]) -> list[_Leaf]:
    if isinstance(node, ast.ClassDef):
        return _split_class(node, lines)
    start, end = _def_start(node), node.end_lineno
    return [_make_leaf(node.name, "\n".join(lines[start - 1 : end]), start, end)]


def _split_class(node: ast.ClassDef, lines: list[str]) -> list[_Leaf]:
    """A class becomes its header (signature + docstring + class-level
    attributes) plus one leaf per method, each still subject to the
    same oversized-splitting pass as any other leaf."""
    methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    class_start, class_end = _def_start(node), node.end_lineno
    if not methods:
        return [_make_leaf(node.name, "\n".join(lines[class_start - 1 : class_end]), class_start, class_end)]

    leaves = []
    header_end = _def_start(methods[0]) - 1
    if header_end >= class_start:
        header_text = "\n".join(lines[class_start - 1 : header_end])
        if header_text.strip():
            leaves.append(_make_leaf(node.name, header_text, class_start, header_end))
    for method in methods:
        for leaf in _leaves_for_def(method, lines):
            leaves.append(dataclasses.replace(leaf, symbol=f"{node.name}.{leaf.symbol}"))
    return leaves


# --- Non-Python: paragraph boundaries --------------------------------------


def _text_leaves(text: str) -> list[_Leaf]:
    leaves = []
    line_cursor = 1
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        n_lines = para.count("\n") + 1
        if para.strip():
            leaves.append(_make_leaf("<module>", para, line_cursor, line_cursor + n_lines - 1))
        line_cursor += n_lines + 1  # +1 for the blank line separator
    return leaves or [_make_leaf("<module>", text, 1, max(text.count("\n") + 1, 1))]


# --- Threshold enforcement: split oversized, merge undersized --------------


def _ensure_within_threshold(leaves: list[_Leaf]) -> list[_Leaf]:
    result = []
    for leaf in leaves:
        if leaf.tokens <= CHUNK_TOKEN_THRESHOLD:
            result.append(leaf)
        else:
            result.extend(_split_lines(leaf))
    return result


def _split_lines(leaf: _Leaf) -> list[_Leaf]:
    """Fall back to packing raw lines into threshold-sized groups. Used
    once a leaf (a whole function, a paragraph, ...) is already too big
    to treat as one chunk. A single line that alone exceeds the
    threshold is kept as its own oversized chunk — there's no coherent
    place left to cut it."""
    parts: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for line in leaf.text.splitlines():
        line_tokens = _count_tokens(line)
        if current and current_tokens + line_tokens > CHUNK_TOKEN_THRESHOLD:
            parts.append(current)
            current, current_tokens = [], 0
        current.append(line)
        current_tokens += line_tokens
    if current:
        parts.append(current)

    result = []
    line_cursor = leaf.start_line
    for i, part in enumerate(parts, start=1):
        result.append(_make_leaf(f"{leaf.symbol}#{i}", "\n".join(part), line_cursor, line_cursor + len(part) - 1))
        line_cursor += len(part)
    return result


def _merge_small(leaves: list[_Leaf]) -> list[_Leaf]:
    """Pack adjacent leaves together while they fit under the threshold,
    so a run of tiny units (short methods, a handful of imports) lands
    in the index as one chunk with real context instead of many."""
    merged: list[_Leaf] = []
    buffer: list[_Leaf] = []
    buffer_tokens = 0

    def flush() -> None:
        if not buffer:
            return
        symbol = buffer[0].symbol if len(buffer) == 1 else " + ".join(leaf.symbol for leaf in buffer)
        merged.append(
            _Leaf(
                symbol=symbol,
                text="\n\n".join(leaf.text for leaf in buffer),
                start_line=buffer[0].start_line,
                end_line=buffer[-1].end_line,
                tokens=buffer_tokens,
            )
        )
        buffer.clear()

    for leaf in leaves:
        if buffer and buffer_tokens + leaf.tokens > CHUNK_TOKEN_THRESHOLD:
            flush()
            buffer_tokens = 0
        buffer.append(leaf)
        buffer_tokens += leaf.tokens
        if buffer_tokens >= CHUNK_TOKEN_THRESHOLD:
            flush()
            buffer_tokens = 0
    flush()
    return merged
