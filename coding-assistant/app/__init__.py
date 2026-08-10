"""
app: Streamlit UI for the coding assistant.

Responsibility:
    The one place allowed to import streamlit. Renders a chat interface
    backed by core.graph.run() for each turn, and drives on-demand code
    execution via services.runner for generated artifacts. Execution is
    a UI-triggered action, not part of the turn graph itself — no
    core.nodes module or AssistantState field represents it, so this is
    the one place app/ reaches past core/ into services/ directly.

    Also owns the one piece of cross-turn state core/ deliberately
    doesn't persist: AssistantState.awaiting_feedback. core.nodes.
    request_solution sets it for the turn that just ran, but nothing
    in services.memory stores it — core/state.py's docstring documents
    who writes each field within a turn, not how a value survives to
    the *next* one, and there's no long-term reason a stale "waiting on
    feedback" flag should outlive a single UI session. Threading it
    into the next request's initial AssistantState is this layer's job,
    and Streamlit's per-session state is exactly where it belongs.

Allowed imports:
    - streamlit
    - core.state, core.graph
    - services.runner (see above)

Must NOT import:
    - core.router, core.nodes.* directly (go through core.graph.run)
    - chromadb, any LLM SDK directly (go through core.graph -> services/)
"""
