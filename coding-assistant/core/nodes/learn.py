"""
core.nodes.learn: persist feedback and memory updates for future turns.

Responsibility:
    Runs the summarize prompt (prompts/summarize.v1.md) and/or profile
    extraction over the completed turn, and persists the results via the
    memory service so that the *next* request's load_memory node picks
    them up. This node does not mutate state.summary or state.profile
    directly — those fields' sole writer is core.nodes.load_memory, at
    the start of the next request. learn.py only writes to persistent
    storage as a side effect through services.memory.

State fields read:
    - thread_id
    - user_message
    - answer
    - artifacts
    - recent_turns

State fields written:
    - none (side effects only, via services.memory; may append to trace)

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/summarize.v1.md by name+version)
    - services.memory (to persist buffer/summary/profile updates)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""
