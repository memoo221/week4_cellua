"""
core.nodes.explain: answer an "explain" intent turn.

Responsibility:
    Runs the explain prompt (prompts/explain.v1.md) to produce a
    natural-language answer for turns classified as explanation requests
    (no retrieval/generation loop involved).

State fields read:
    - user_message
    - attached_code
    - language
    - recent_turns
    - summary
    - profile

State fields written (sole writer, per core/state.py):
    - answer

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/explain.v1.md by name+version)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""
