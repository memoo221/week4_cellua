"""
core.nodes.grade: judge relevance of retrieved chunks before generation.

Responsibility:
    Runs the grade prompt (prompts/grade.v1.md) against each retrieved
    chunk, filters down to the relevant subset, and produces an overall
    grade that core.router uses to decide whether to proceed to generate
    or loop back to retrieve (bounded by retry_count).

State fields read:
    - user_message
    - retrieved_chunks

State fields written (sole writer, per core/state.py):
    - chunk_grades
    - relevant_chunks
    - overall_grade

Allowed imports:
    - core.state, core.types
    - services.llm (referencing prompts/grade.v1.md by name+version)

Must NOT import:
    - streamlit, fastapi, chromadb, any LLM SDK directly
    - other core.nodes modules
"""
