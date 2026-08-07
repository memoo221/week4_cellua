"""
core.nodes.retrieve: fetch candidate context chunks for a "generate" turn.

Responsibility:
    Embeds the user's query and fetches the top-k candidate chunks from
    the vector store, ahead of grading.

State fields read:
    - user_message
    - attached_code
    - language

State fields written (sole writer, per core/state.py):
    - retrieved_chunks

Allowed imports:
    - core.state, core.types
    - services.embeddings, services.vectorstore

Must NOT import:
    - streamlit, fastapi, chromadb directly (only via services.vectorstore)
    - any LLM SDK directly
    - other core.nodes modules
"""
