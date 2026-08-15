

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:

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
    dataset_db_path: str = str


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
        dataset_db_path=os.environ.get("DATASET_DB_PATH", "data/datasets.db"),
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
