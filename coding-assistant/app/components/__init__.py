"""
app/components: reusable Streamlit rendering helpers.

Responsibility:
    Small, focused render functions used by app/streamlit_app.py so the
    main script stays a readable top-to-bottom flow (input -> run turn
    -> render output) instead of a wall of widget code.

Allowed imports:
    - streamlit
    - core.types (Artifact — the shape these components render)
    - services.runner (artifact_view.py's "run" button)

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
"""
