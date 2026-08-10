"""
app/components/chat.py: chat message rendering and response streaming.

Responsibility:
    Render one message bubble (history replay or a fresh turn) and
    provide stream_words(), the generator streamlit_app.py hands to
    st.write_stream() for the "response streaming" requirement.

    stream_words() is a UI-level reveal, not token-level model
    streaming: core.graph.run() doesn't return anything until the
    entire turn (classify -> retrieve -> grade -> generate, each a
    blocking HTTP call) has finished, and generate's output is parsed
    JSON — there is no well-formed partial value to show mid-request.
    Streaming the already-complete answer word-by-word is what's
    actually available to stream without changing that contract; see
    the app/__init__.py docstring for the broader app/core boundary
    this respects.
"""

from __future__ import annotations

import time
from typing import Iterator

import streamlit as st

from app.components.artifact_view import render_artifact
from core.types import Artifact

# Delay between words for stream_words()'s reveal effect. Small enough
# not to feel sluggish on a long answer, large enough to actually read
# as "streaming" rather than an instant paste.
_STREAM_DELAY_SECONDS = 0.02


def stream_words(text: str) -> Iterator[str]:
    """Yield `text` one word at a time, for st.write_stream().

    Args:
        text: the complete, already-generated answer.

    Yields:
        Each word (with a trailing space, so joined output reads
        naturally), paced by _STREAM_DELAY_SECONDS.
    """
    for word in text.split(" "):
        yield word + " "
        time.sleep(_STREAM_DELAY_SECONDS)


def render_message(role: str, content: str, artifacts: list[Artifact], message_key: str) -> None:
    """Render one historical message bubble: text plus any artifacts.

    Used for replaying past turns from st.session_state.messages. The
    newest turn is rendered separately by streamlit_app.py so it can
    stream via stream_words() instead of appearing all at once.

    Args:
        role: "user" or "assistant".
        content: the message text.
        artifacts: code blocks attached to this message, if any.
        message_key: a value unique to this message's position in the
            conversation (e.g. its index in st.session_state.messages).
            Passed through to render_artifact so two turns that happen
            to produce byte-identical code — same language, same code,
            hence the same content-hashed Artifact.id from
            services/artifacts.py — don't collide on Streamlit widget
            keys when both get rendered in the same script run. Without
            this, that collision raises StreamlitDuplicateElementKey and
            crashes the whole page (reproduced while fixing this).
    """
    with st.chat_message(role):
        st.markdown(content)
        for i, artifact in enumerate(artifacts):
            render_artifact(artifact, key_prefix=f"{message_key}-{i}")
