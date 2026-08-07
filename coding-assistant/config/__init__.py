"""
config: environment-driven runtime configuration.

Responsibility:
    Houses settings.py, the single source of truth for values read from
    the environment (DB paths, model config, retrieval parameters).

Allowed imports:
    - stdlib only

Must NOT import:
    - core.*, services.*, app/, api/ (a leaf every other layer may depend
      on, never the reverse)
"""
