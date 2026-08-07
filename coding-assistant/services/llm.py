"""
services/llm.py: LLM provider adapter (OpenRouter) and per-task model routing.

Responsibility:
    Wraps OpenRouter's OpenAI-compatible API behind a single interface
    that core.nodes call by task (classifier / grader / generator /
    summarizer), each configured with its own model, temperature, and
    max_tokens (see config/settings.py). Loads prompt templates from
    prompts/ by name+version and fills in template variables — prompt
    text itself never lives in this file. Also exposes list_free_models
    so a task can be pointed at a $0-priced OpenRouter model when no
    specific model is configured.

Allowed imports:
    - stdlib
    - requests (the chosen HTTP client for OpenRouter's REST API)
    - core.types (Turn — read-only, for type hints on classifier input)
    - config.settings

Must NOT import:
    - core.state, core.router, core.graph, core.nodes.*
    - streamlit, fastapi, chromadb
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from config.settings import get_settings
from core.types import Turn

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Prompt referenced by name+version only — the text itself lives in
# prompts/classifier.v1.md, never inline here.
CLASSIFIER_PROMPT = "classifier.v1"

# TODO(later phase): CLASSIFIER_PROMPT's sibling constants — GRADER_PROMPT
# = "grade.v1", GENERATOR_PROMPT = "generate.v1", SUMMARIZER_PROMPT =
# "summarize.v1" — land alongside their respective nodes.


def list_free_models() -> list[str]:
    """List OpenRouter model ids priced at zero for prompt and completion.

    Calls OpenRouter's public GET /models endpoint — no API key required
    just to list.

    Returns:
        Free model ids (e.g. "some-org/some-model:free"), in whatever
        order OpenRouter's API returns them.

    Failure modes:
        requests.RequestException on a network/HTTP failure.
    """
    base_url = get_settings().openrouter_base_url
    response = requests.get(f"{base_url}/models", timeout=15)
    response.raise_for_status()
    models = response.json()["data"]
    return [
        m["id"]
        for m in models
        if m.get("pricing", {}).get("prompt") == "0" and m.get("pricing", {}).get("completion") == "0"
    ]


def _default_model() -> str:
    """Fall back to some free model when a call site has none configured.

    Returns:
        The first currently-free OpenRouter model id.

    Failure modes:
        requests.RequestException if the underlying list_free_models
        call fails. IndexError if OpenRouter currently lists none free.
    """
    return list_free_models()[0]


def _load_prompt(name: str) -> str:
    """Read a versioned prompt template's raw text from prompts/.

    Args:
        name: e.g. "classifier.v1" for prompts/classifier.v1.md.

    Returns:
        The template file's raw contents.

    Failure modes:
        FileNotFoundError if the named prompt file doesn't exist yet.
    """
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _chat_completion(
    model: str, system_prompt: str, user_content: str, temperature: float, max_tokens: int
) -> str:
    """Call OpenRouter's /chat/completions and return the reply text.

    Args:
        model: OpenRouter model id.
        system_prompt: the loaded prompt template text, sent as the
            system message.
        user_content: request-specific content (the filled-in template
            variables), sent as the user message.
        temperature: sampling temperature.
        max_tokens: max output tokens.

    Returns:
        The first choice's message content.

    Failure modes:
        RuntimeError if OPENROUTER_API_KEY isn't configured.
        requests.RequestException on a network/HTTP failure.
        KeyError/IndexError if the response body doesn't have the
        expected shape.
    """
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; see .env.example")
    response = requests.post(
        f"{settings.openrouter_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def run_classifier(
    user_message: str,
    attached_code: str | None,
    recent_turns: list[Turn],
    summary: str | None,
) -> tuple[str, float, str | None]:
    """Classify a turn's intent and (if code is present) its language.

    Loads prompts/classifier.v1.md as the system prompt, sends the given
    context as the user message, and parses the model's JSON reply per
    that prompt's Output contract.

    Args:
        user_message: the user's raw message this turn.
        attached_code: code the user attached, if any.
        recent_turns: buffer-tier conversation history for context.
        summary: rolling summary of older turns, if any.

    Returns:
        A (intent, intent_confidence, language) tuple, per
        prompts/classifier.v1.md's Output contract.

    Failure modes:
        RuntimeError if no API key is configured.
        FileNotFoundError if the prompt template is missing.
        requests.RequestException on a network/HTTP failure.
        json.JSONDecodeError / KeyError if the model's reply doesn't
        match the documented Output contract.
    """
    settings = get_settings()
    model = settings.classifier_model or _default_model()
    system_prompt = _load_prompt(CLASSIFIER_PROMPT)
    user_content = json.dumps(
        {
            "user_message": user_message,
            "attached_code": attached_code,
            "recent_turns": [turn.__dict__ for turn in recent_turns],
            "summary": summary,
        }
    )
    reply = _chat_completion(
        model, system_prompt, user_content, settings.classifier_temperature, settings.classifier_max_tokens
    )
    parsed = json.loads(reply)
    return parsed["intent"], float(parsed["intent_confidence"]), parsed.get("language")
