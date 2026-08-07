"""
core/graph.py: node + edge wiring — the only file that knows the shape.

Responsibility:
    Assemble the individual nodes in core/nodes/ into a runnable graph,
    using core.router to decide edges. This is the single place that
    knows the overall control flow; nodes themselves never call each
    other, and router.py never sequences anything — it only answers
    "what's next" for one state.

    The graph-framework decision (hand-rolled loop vs. LangGraph vs.
    something else) is DEFERRED. Do not add langgraph or langchain as a
    dependency yet. This file is an abstract wiring stub until that
    decision is made.

Allowed imports:
    - stdlib only
    - core.state, core.router, core.nodes.* (once nodes exist)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK
    - langgraph, langchain, or any orchestration framework (until the
      framework decision above is explicitly made)
    - anything from services/, app/, api/ directly (nodes talk to
      services/, graph.py only sequences nodes)

Contract:
    Whatever shape this takes, it must preserve: nodes have signature
    `(state: AssistantState) -> dict`, nodes never call each other, and
    the state fields each node reads/writes stay as documented in
    core/state.py.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

from core import router
from core.nodes import classify, load_memory
from core.state import AssistantState

# A node is any callable matching this shape: read the whole state, return
# only the fields it writes. graph.py is the only place that turns a bare
# node name into an actual callable.
NodeFn = Callable[[AssistantState], dict]

# Fixed step names. Unlike CLASSIFY/EXPLAIN/RETRIEVE/GRADE/GENERATE (which
# core.router.route() chooses between dynamically), these three always run
# at a fixed point in the turn — they are never a routing decision, so
# core.router has no opinion about them.
LOAD_MEMORY = "load_memory"
REQUEST_SOLUTION = "request_solution"
LEARN = "learn"

# TODO(phase 2+): register the remaining nodes as they're implemented.
# Keys must cover every core.router node-name constant plus LOAD_MEMORY,
# REQUEST_SOLUTION, and LEARN above.
NODE_REGISTRY: dict[str, NodeFn] = {
    LOAD_MEMORY: load_memory.run,
    router.CLASSIFY: classify.run,
}

# Once core.router.route() returns one of these, the node it names produces
# a final answer for the turn (an explanation or a generated artifact) —
# the router-driven loop stops and the fixed post-steps below take over.
_TERMINAL_NODES = (router.EXPLAIN, router.GENERATE)


def _apply(state: AssistantState, node_name: str) -> AssistantState:
    """Call one node by name and merge its returned fields into `state`.

    Looks `node_name` up in NODE_REGISTRY, calls it with `state`, and
    merges the dict it returns back in — nodes only ever return the
    fields they own (see core/state.py), so this is a partial update,
    never a replacement of the whole state.

    Args:
        state: the state to update.
        node_name: key into NODE_REGISTRY.

    Returns:
        A new AssistantState with the node's returned fields applied.

    Failure modes:
        KeyError if `node_name` isn't registered; whatever the node
        itself raises (e.g. NotImplementedError, until phase 1).
    """
    update = NODE_REGISTRY[node_name](state)
    return dataclasses.replace(state, **update)


def run(state: AssistantState) -> AssistantState:
    """Drive `state` through one full turn of the graph.

    Fixed shape, framework-free (see module docstring): load_memory
    always runs first; classify runs next unless state.awaiting_feedback
    is True (core.router's feedback-bypass rule — see core/router.py);
    then core.router.route() is consulted in a loop to walk the
    retrieve/grade/generate-or-explain path until it names a terminal
    node; finally request_solution (only if artifacts were produced) and
    learn always close out the turn.

    Args:
        state: the initial AssistantState for one request, as constructed
            by the caller in app/ or api/.

    Returns:
        The final AssistantState once the turn's fixed post-steps have
        run.

    Failure modes:
        Whatever the underlying nodes raise — this function does not
        catch or retry node failures itself.
    """
    state = _apply(state, LOAD_MEMORY)

    if not state.awaiting_feedback:
        state = _apply(state, router.CLASSIFY)

    next_node = router.route(state)
    while next_node not in _TERMINAL_NODES:
        state = _apply(state, next_node)
        next_node = router.route(state)
    state = _apply(state, next_node)

    if state.artifacts:
        state = _apply(state, REQUEST_SOLUTION)
    return _apply(state, LEARN)
