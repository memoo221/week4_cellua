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
        explainer_model: model id used for the explain call site. Empty
            string means "pick a free model at call time" (see
            services.llm).
        explainer_temperature: sampling temperature for the explainer.
        explainer_max_tokens: max output tokens for the explainer.
        jina_api_key: auth for Jina AI's hosted embeddings API. Unlike
            openrouter_api_key, there's no key-free path for embeddings —
            required by services.embeddings.
        jina_base_url: Jina AI's embeddings API root.
        embedding_model: Jina model id used for both indexing
            (ingestion/build_index.py) and query-time retrieval
            (core.nodes.retrieve) — see services/embeddings.py for why
            both paths must share one model.
        chroma_path: filesystem path to the on-disk Chroma database.
        collection_name: Chroma collection holding the ingested Chunks.
        top_k: number of candidate chunks core.nodes.retrieve asks the
            vector store for, before grading.
        rerank_top_n: number of graded chunks kept for generation, once
            reranking (if any) narrows the top_k candidates down.
        grader_model: model id used for the grade call site. Empty
            string means "pick a free model at call time" (see
            services.llm).
        grader_temperature: sampling temperature for the grader.
        grader_max_tokens: max output tokens for the grader.
        generator_model: model id used for the generate call site. Empty
            string means "pick a free model at call time" (see
            services.llm).
        generator_temperature: sampling temperature for the generator.
        generator_max_tokens: max output tokens for the generator.
        summarizer_model: model id used for the learn call site. Empty
            string means "pick a free model at call time" (see
            services.llm).
        summarizer_temperature: sampling temperature for the summarizer.
        summarizer_max_tokens: max output tokens for the summarizer.
    """

    memory_db_path: str
    openrouter_api_key: str | None
    openrouter_base_url: str
    classifier_model: str
    classifier_temperature: float
    classifier_max_tokens: int
    explainer_model: str
    explainer_temperature: float
    explainer_max_tokens: int
    jina_api_key: str | None
    jina_base_url: str
    embedding_model: str
    chroma_path: str
    collection_name: str
    top_k: int
    rerank_top_n: int
    grader_model: str
    grader_temperature: float
    grader_max_tokens: int
    generator_model: str
    generator_temperature: float
    generator_max_tokens: int
    summarizer_model: str
    summarizer_temperature: float
    summarizer_max_tokens: int


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
        classifier_max_tokens=int(os.environ.get("CLASSIFIER_MAX_TOKENS", "600")),
        explainer_model=os.environ.get("EXPLAINER_MODEL", ""),
        explainer_temperature=float(os.environ.get("EXPLAINER_TEMPERATURE", "0.2")),
        explainer_max_tokens=int(os.environ.get("EXPLAINER_MAX_TOKENS", "800")),
        jina_api_key=os.environ.get("JINA_API_KEY") or None,
        jina_base_url=os.environ.get("JINA_BASE_URL", "https://api.jina.ai/v1"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "jina-embeddings-v2-base-code"),
        chroma_path=os.environ.get("CHROMA_PATH", "data/chroma"),
        collection_name=os.environ.get("COLLECTION_NAME", "coding_assistant"),
        top_k=int(os.environ.get("TOP_K", "8")),
        rerank_top_n=int(os.environ.get("RERANK_TOP_N", "4")),
        grader_model=os.environ.get("GRADER_MODEL", ""),
        grader_temperature=float(os.environ.get("GRADER_TEMPERATURE", "0.0")),
        grader_max_tokens=int(os.environ.get("GRADER_MAX_TOKENS", "1200")),
        generator_model=os.environ.get("GENERATOR_MODEL", ""),
        generator_temperature=float(os.environ.get("GENERATOR_TEMPERATURE", "0.2")),
        generator_max_tokens=int(os.environ.get("GENERATOR_MAX_TOKENS", "1800")),
        summarizer_model=os.environ.get("SUMMARIZER_MODEL", ""),
        summarizer_temperature=float(os.environ.get("SUMMARIZER_TEMPERATURE", "0.2")),
        summarizer_max_tokens=int(os.environ.get("SUMMARIZER_MAX_TOKENS", "600")),
    )
