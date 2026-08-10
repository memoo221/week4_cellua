"""
core/router.py: the pure routing policy.

Responsibility:
    Decide which node runs next, given only the current AssistantState.
    This is the one file that encodes "what happens when" as data-driven
    logic, separate from graph wiring (which encodes "how nodes connect").

    Signature (to implement): `(state: AssistantState) -> str`, returning
    the name of the next node.

    Cases this must handle once implemented:
      - intent == "explain"                 -> route to the explain node
      - intent == "generate"                -> route to the retrieve/generate
                                                path
      - intent is None / unknown / below a
        confidence threshold                -> route to a clarification or
                                                fallback node
      - state.awaiting_feedback is True      -> route to whatever handles
                                                user feedback on a pending
                                                artifact, bypassing
                                                classification
      - state.awaiting_teaching is True      -> route to whatever persists
                                                the user's taught answer,
                                                bypassing classification
      - state.retry_count exceeds a bound    -> route to a terminal/give-up
                                                node instead of looping
                                                generate/grade forever

Allowed imports:
    - stdlib only (typing)
    - core.state (for the AssistantState type)

Must NOT import:
    - anything from services/ (no I/O, no LLM calls — this function must
      be a pure, synchronous, side-effect-free mapping from state to a
      node name string)
    - streamlit, fastapi, chromadb, any LLM SDK
    - core.graph (router is a leaf; graph depends on router, not the
      reverse)

Why pure:
    This function is exhaustively unit-testable (tests/test_router.py)
    without mocking any I/O, and its purity is itself a guardrail enforced
    by tests/test_architecture.py.
"""

from __future__ import annotations

from core.state import AssistantState

# Node-name constants. These must exactly match the keys core.graph puts
# in NODE_REGISTRY (in turn, the module names under core/nodes/).
CLASSIFY = "classify"
EXPLAIN = "explain"
RETRIEVE = "retrieve"
GRADE = "grade"
GENERATE = "generate"
ASK_FOR_HELP = "ask_for_help"
LEARN_TAUGHT_FACT = "learn_taught_fact"

# Below this, classify's result isn't trusted enough to act on.
CONFIDENCE_THRESHOLD = 0.5

# Retrieve/grade loop bound. Once state.retry_count exceeds this, stop
# retrying and ask the user for the correct answer (core.nodes.
# ask_for_help) rather than loop on a low-quality retrieval forever, or
# generate an answer from context that was never actually relevant.
MAX_RETRIES = 2


def route(state: AssistantState) -> str:
    """Decide which node core.graph should call next for `state`.

    Pure function: reads `state` only, performs no I/O, and is total —
    every reachable combination of fields maps to a node name, so this
    never raises. See core/graph.py for how the returned name is
    resolved to a callable, and core/state.py for the field-ownership
    rules this decision relies on.

    Args:
        state: the current AssistantState, already updated with the
            previous node's returned fields.

    Returns:
        The name of the next node to run.
    """
    # 1. The user is answering a question core.nodes.ask_for_help just
    # asked them — this takes priority over everything else, including
    # re-classification: it's not a fresh request, it's the taught fact
    # this turn exists to persist.
    if state.awaiting_teaching:
        return LEARN_TAUGHT_FACT

    # 2. A pending artifact awaiting the user's feedback takes priority
    # over everything else, including re-classification: the reply is
    # fed straight back into generation instead of being reclassified.
    if state.awaiting_feedback:
        return GENERATE

    # 3. No usable intent yet — unset, unrecognized, or too low-confidence
    # to act on — falls back to a plain explanatory answer rather than
    # guessing at code generation.
    known_intents = (EXPLAIN, GENERATE)
    if state.intent not in known_intents or state.intent_confidence < CONFIDENCE_THRESHOLD:
        return EXPLAIN

    # 4. Explain intent: answer directly, no retrieval involved.
    if state.intent == EXPLAIN:
        return EXPLAIN

    # 5. Generate intent: walk retrieve -> grade -> generate. A grade of
    # "insufficient" loops back to retrieve, bounded by retry_count —
    # once that bound is hit, ask the user for help instead of letting
    # generate hallucinate from context that was never actually relevant.
    if not state.retrieved_chunks:
        return RETRIEVE
    if state.overall_grade is None:
        return GRADE
    if state.overall_grade == "insufficient":
        if state.retry_count > MAX_RETRIES:
            return ASK_FOR_HELP
        return RETRIEVE
    return GENERATE
