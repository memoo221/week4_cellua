"""
core.nodes.generate: produce a code answer for a "generate" intent turn.

Responsibility:
    Runs the generate prompt (prompts/generate.v1.md) using the graded,
    relevant chunks as context, and packages any resulting code into
    Artifacts via the artifacts service.

State fields read:
    - user_message
    - attached_code
    - language
    - relevant_chunks
    - recent_turns
    - summary
    - profile

State fields written (sole writer, per core/state.py):
    - answer
    - artifacts

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/generate.v1.md by name+version)
    - services.artifacts (to register generated code blocks by id)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""
