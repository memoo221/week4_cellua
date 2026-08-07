"""
config/settings.py: environment-driven settings.

Responsibility:
    Single source of truth for runtime configuration, read from
    environment variables (see .env.example). Eventually holds
    per-call-site model config (classifier/grader/generator/summarizer),
    embedding_model, chroma_path, collection_name, top_k, rerank_top_n —
    that full shape is deferred until config is wired up end to end.
    For now it exposes just what services/memory.py needs.

Allowed imports:
    - stdlib only

Must NOT import:
    - core.*, services.*, app/, api/ (settings is a leaf every layer may
      depend on; it must never depend back on them)
    - streamlit, fastapi, chromadb, any LLM SDK
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, sourced from environment variables.

    Attributes:
        memory_db_path: filesystem path to the SQLite database backing
            services/memory.py's buffer, summary, and profile tiers.
        openrouter_api_key: auth for OpenRouter chat completions. Not
            required just to list models (services.llm.list_free_models).
        openrouter_base_url: OpenRouter's OpenAI-compatible API root.
        classifier_model: model id used for the classifier call site.
            Empty string means "pick a free model at call time" (see
            services.llm).
        classifier_temperature: sampling temperature for the classifier.
        classifier_max_tokens: max output tokens for the classifier.

    # TODO(later phase): add embedding_model, chroma_path,
    # collection_name, top_k, rerank_top_n, and the remaining
    # per-call-site model config (grader/generator/summarizer), each with
    # its own temperature and max_tokens, once those services land.
    """

    memory_db_path: str
    openrouter_api_key: str | None
    openrouter_base_url: str
    classifier_model: str
    classifier_temperature: float
    classifier_max_tokens: int


@lru_cache
def get_settings() -> Settings:
    """Build (and cache) the Settings instance from environment variables.

    Returns:
        A Settings populated from os.environ, falling back to defaults
        suitable for local development.

    Failure modes:
        None — every field has a default, so this never raises.
    """
    return Settings(
        memory_db_path=os.environ.get("MEMORY_DB_PATH", "data/memory.db"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
        openrouter_base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        classifier_model=os.environ.get("CLASSIFIER_MODEL", ""),
        classifier_temperature=float(os.environ.get("CLASSIFIER_TEMPERATURE", "0.0")),
        classifier_max_tokens=int(os.environ.get("CLASSIFIER_MAX_TOKENS", "200")),
    )
