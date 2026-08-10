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
    - core.types (Turn, Chunk, Artifact — read-only, for type hints on
      classifier/grader/summarizer input)
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
from core.types import Artifact, Chunk, Turn

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Prompts referenced by name+version only — the text itself lives in
# prompts/*.md, never inline here.
CLASSIFIER_PROMPT = "classifier.v1"
EXPLAINER_PROMPT = "explain.v1"
GRADER_PROMPT = "grade.v1"
GENERATOR_PROMPT = "generate.v1"
SUMMARIZER_PROMPT = "summarize.v1"


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


def _resilient_chat_completion(
    configured_model: str, system_prompt: str, user_content: str, temperature: float, max_tokens: int
) -> str:
    """Run a chat completion, falling back across free models if unpinned.

    If a call site has a specific model configured, use it directly —
    an operator who pinned a model gets exactly that model, no silent
    substitution. Otherwise, try OpenRouter's currently-free models in
    listed order until one returns usable content: the $0-priced list
    is unvetted (it can include non-chat models, e.g. music-generation
    ones, and heavy-reasoning models that burn max_tokens on chain-of-
    thought and return null content — see _chat_completion), so a
    single blind pick at index 0 isn't reliable enough to build on.

    Args:
        configured_model: an explicit model id, or "" to auto-pick.
        system_prompt, user_content, temperature, max_tokens: passed
            through to _chat_completion for each attempt.

    Returns:
        The first successful reply's content.

    Failure modes:
        Whatever _chat_completion raises, if configured_model is set.
        RuntimeError if every free model fails when auto-picking.
        requests.RequestException if listing free models itself fails.
    """
    if configured_model:
        return _chat_completion(configured_model, system_prompt, user_content, temperature, max_tokens)

    last_error: Exception | None = None
    for model in list_free_models():
        try:
            return _chat_completion(model, system_prompt, user_content, temperature, max_tokens)
        except (RuntimeError, requests.RequestException) as error:
            last_error = error
            continue
    raise RuntimeError(f"every free OpenRouter model failed; last error: {last_error}") from last_error


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
        RuntimeError if OPENROUTER_API_KEY isn't configured, or if the
        model returned no content — some free models spend max_tokens
        on internal reasoning before ever emitting content, which comes
        back null if the budget runs out mid-reasoning; the caller
        should raise its own max_tokens for that call site.
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
            # These are short, structured (often JSON) outputs, not tasks
            # that benefit from extended reasoning — cap it low so
            # reasoning-capable free models don't burn the whole
            # max_tokens budget on chain-of-thought before ever emitting
            # content. Silently ignored by models without reasoning.
            "reasoning": {"effort": "low"},
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if content is None:
        raise RuntimeError(
            f"{model} returned no content (max_tokens={max_tokens} likely exhausted by reasoning "
            "output before any content was emitted) — try a higher max_tokens for this call site"
        )
    return content


def _strip_json_fence(reply: str) -> str:
    """Strip a ```json ... ``` (or bare ``` ... ```) wrapper if present.

    Prompts that demand raw JSON (e.g. prompts/classifier.v1.md) are not
    reliably followed by smaller/free models, which often wrap their
    reply in a markdown code fence anyway. Stripping it here keeps that
    model behavior from being a parse error at every JSON-output call
    site, rather than relying on prompt wording alone.

    Args:
        reply: the raw model reply.

    Returns:
        `reply` with a single leading/trailing code fence removed, or
        `reply.strip()` unchanged if it wasn't fenced.
    """
    text = reply.strip()
    if not text.startswith("```"):
        return text
    text = text.removeprefix("```json").removeprefix("```").strip()
    return text.removesuffix("```").strip()


# How many times a JSON-output call site retries after a malformed reply
# before giving up. Small/free models occasionally emit invalid JSON when
# a value embeds a large multi-line code block (an unescaped quote, a
# stray trailing brace); since these calls run at temperature > 0 much of
# the time, a fresh attempt commonly succeeds where the last one didn't.
_JSON_RETRY_ATTEMPTS = 3


def _call_json(
    configured_model: str, system_prompt: str, user_content: str, temperature: float, max_tokens: int
) -> dict:
    """Run a chat completion and parse its reply as JSON, with retries.

    Args:
        configured_model, system_prompt, user_content, temperature,
            max_tokens: passed through to _resilient_chat_completion.

    Returns:
        The parsed JSON object.

    Failure modes:
        Whatever _resilient_chat_completion raises.
        RuntimeError if every attempt's reply fails to parse as JSON.
        KeyError if the parsed JSON is missing a key the caller expects
        (not retried — a schema violation, not a malformed-JSON one).
    """
    last_error: json.JSONDecodeError | None = None
    last_reply = ""
    for _ in range(_JSON_RETRY_ATTEMPTS):
        last_reply = _resilient_chat_completion(configured_model, system_prompt, user_content, temperature, max_tokens)
        try:
            return json.loads(_strip_json_fence(last_reply))
        except json.JSONDecodeError as error:
            last_error = error
            continue
    raise RuntimeError(
        f"model reply wasn't valid JSON after {_JSON_RETRY_ATTEMPTS} attempts; last error: {last_error}; "
        f"last reply: {last_reply!r}"
    ) from last_error


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
    system_prompt = _load_prompt(CLASSIFIER_PROMPT)
    user_content = json.dumps(
        {
            "user_message": user_message,
            "attached_code": attached_code,
            "recent_turns": [turn.__dict__ for turn in recent_turns],
            "summary": summary,
        }
    )
    parsed = _call_json(
        settings.classifier_model, system_prompt, user_content, settings.classifier_temperature,
        settings.classifier_max_tokens,
    )
    return parsed["intent"], float(parsed["intent_confidence"]), parsed.get("language")


def run_explainer(
    user_message: str,
    attached_code: str | None,
    language: str | None,
    recent_turns: list[Turn],
    summary: str | None,
    profile: dict[str, str],
) -> str:
    """Answer an "explain" intent turn with a natural-language response.

    Loads prompts/explain.v1.md as the system prompt, sends the given
    context as the user message, and returns the model's reply verbatim
    per that prompt's Output contract (plain text, not JSON).

    Args:
        user_message: the user's raw message this turn.
        attached_code: code the user attached, if any.
        language: the turn's detected/declared code language, if any.
        recent_turns: buffer-tier conversation history for context.
        summary: rolling summary of older turns, if any.
        profile: long-lived user profile facts, if any.

    Returns:
        The model's reply text, to be stored verbatim as state.answer.

    Failure modes:
        RuntimeError if no API key is configured.
        FileNotFoundError if the prompt template is missing.
        requests.RequestException on a network/HTTP failure.
        KeyError/IndexError if the response body doesn't have the
        expected shape.
    """
    settings = get_settings()
    system_prompt = _load_prompt(EXPLAINER_PROMPT)
    user_content = json.dumps(
        {
            "user_message": user_message,
            "attached_code": attached_code,
            "language": language,
            "recent_turns": [turn.__dict__ for turn in recent_turns],
            "summary": summary,
            "profile": profile,
        }
    )
    return _resilient_chat_completion(
        settings.explainer_model, system_prompt, user_content, settings.explainer_temperature,
        settings.explainer_max_tokens,
    )


def run_grader(user_message: str, retrieved_chunks: list[Chunk]) -> tuple[dict[str, str], str]:
    """Grade retrieved chunks' relevance to a "generate" intent turn.

    Loads prompts/grade.v1.md as the system prompt, sends the user's
    request plus each candidate chunk as the user message, and parses
    the model's JSON reply per that prompt's Output contract.

    Args:
        user_message: the user's raw message this turn — what the
            eventual generate call must answer.
        retrieved_chunks: candidates from core.nodes.retrieve.

    Returns:
        A (chunk_grades, overall_grade) tuple: chunk_grades maps each
        input chunk's id to "relevant"/"irrelevant" (per
        prompts/grade.v1.md, every id is graded); overall_grade is
        "sufficient" or "insufficient".

    Failure modes:
        RuntimeError if no API key is configured.
        FileNotFoundError if the prompt template is missing.
        requests.RequestException on a network/HTTP failure.
        json.JSONDecodeError / KeyError if the model's reply doesn't
        match the documented Output contract.
    """
    settings = get_settings()
    system_prompt = _load_prompt(GRADER_PROMPT)
    user_content = json.dumps(
        {
            "user_message": user_message,
            "chunks": [
                {"id": c.id, "symbol": c.metadata.get("symbol", ""), "source": c.source, "text": c.text}
                for c in retrieved_chunks
            ],
        }
    )
    parsed = _call_json(
        settings.grader_model, system_prompt, user_content, settings.grader_temperature, settings.grader_max_tokens
    )
    return parsed["chunk_grades"], parsed["overall_grade"]


def run_generator(
    user_message: str,
    attached_code: str | None,
    language: str | None,
    relevant_chunks: list[Chunk],
    recent_turns: list[Turn],
    summary: str | None,
    profile: dict[str, str],
) -> tuple[str, list[dict]]:
    """Generate code (and an explanation) for a "generate" intent turn.

    Loads prompts/generate.v1.md as the system prompt, sends the given
    context as the user message, and parses the model's JSON reply per
    that prompt's Output contract.

    Args:
        user_message: the user's raw message this turn.
        attached_code: code the user attached, if any.
        language: the turn's detected/declared code language, if any.
        relevant_chunks: graded-relevant context from core.nodes.grade.
        recent_turns: buffer-tier conversation history for context.
        summary: rolling summary of older turns, if any.
        profile: long-lived user profile facts, if any.

    Returns:
        An (answer, artifact_specs) tuple: answer is the natural-
        language reply text; artifact_specs is the raw list of
        {"language", "code", "description"} dicts, per
        prompts/generate.v1.md's Output contract — core.nodes.generate
        is responsible for turning each into an Artifact via
        services.artifacts.make_artifact.

    Failure modes:
        RuntimeError if no API key is configured.
        FileNotFoundError if the prompt template is missing.
        requests.RequestException on a network/HTTP failure.
        json.JSONDecodeError / KeyError if the model's reply doesn't
        match the documented Output contract.
    """
    settings = get_settings()
    system_prompt = _load_prompt(GENERATOR_PROMPT)
    user_content = json.dumps(
        {
            "user_message": user_message,
            "attached_code": attached_code,
            "language": language,
            "relevant_chunks": [
                {"symbol": c.metadata.get("symbol", ""), "source": c.source, "text": c.text}
                for c in relevant_chunks
            ],
            "recent_turns": [turn.__dict__ for turn in recent_turns],
            "summary": summary,
            "profile": profile,
        }
    )
    parsed = _call_json(
        settings.generator_model, system_prompt, user_content, settings.generator_temperature,
        settings.generator_max_tokens,
    )
    return parsed["answer"], parsed["artifacts"]


def run_summarizer(
    user_message: str,
    answer: str | None,
    artifacts: list[Artifact],
    recent_turns: list[Turn],
    existing_summary: str | None,
    existing_profile: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Fold a completed turn into the thread's rolling summary/profile.

    Loads prompts/summarize.v1.md as the system prompt, sends the
    completed turn plus the thread's existing memory as the user
    message, and parses the model's JSON reply per that prompt's Output
    contract.

    Args:
        user_message: this turn's user message.
        answer: this turn's assistant answer, if any.
        artifacts: code produced this turn, if any — only language and
            description are sent, not the full code (see
            prompts/summarize.v1.md).
        recent_turns: buffer-tier conversation history, for context on
            what's already covered verbatim.
        existing_summary: the thread's current rolling summary, if any.
        existing_profile: durable facts about this user so far.

    Returns:
        An (updated_summary, profile_updates) tuple, per
        prompts/summarize.v1.md's Output contract. core.nodes.learn is
        responsible for persisting both via services.memory — this
        function only produces the new values, it doesn't write them.

    Failure modes:
        RuntimeError if no API key is configured.
        FileNotFoundError if the prompt template is missing.
        requests.RequestException on a network/HTTP failure.
        json.JSONDecodeError / KeyError if the model's reply doesn't
        match the documented Output contract.
    """
    settings = get_settings()
    system_prompt = _load_prompt(SUMMARIZER_PROMPT)
    user_content = json.dumps(
        {
            "existing_summary": existing_summary,
            "existing_profile": existing_profile,
            "recent_turns": [turn.__dict__ for turn in recent_turns],
            "user_message": user_message,
            "answer": answer,
            "artifacts": [{"language": a.language, "description": a.description} for a in artifacts],
        }
    )
    parsed = _call_json(
        settings.summarizer_model, system_prompt, user_content, settings.summarizer_temperature,
        settings.summarizer_max_tokens,
    )
    return parsed["summary"], parsed["profile_updates"]
