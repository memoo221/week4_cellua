"""
app/streamlit_app.py: Streamlit chat UI for the coding assistant.

Run with (from coding-assistant/): `streamlit run app/streamlit_app.py`

Responsibility:
    Wires a chat interface to core.graph.run() for each turn: renders
    history, takes the next user message (plus an optional attached
    file), drives one turn of the graph, and renders the result
    (streamed text + any executable code artifacts). See
    app/__init__.py for the app/core/services boundary this keeps, and
    app/components/chat.py for why "streaming" here means revealing an
    already-complete answer rather than token-level model streaming.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Streamlit's `streamlit run` only puts this file's own directory
# (app/) on sys.path, not the project root — so the absolute imports
# below (app.components.*, core.*) can't resolve unless the root is
# added explicitly, regardless of the caller's cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

# config/settings.py only reads os.environ — it never loads .env itself
# (its own docstring restricts it to stdlib-only imports), and there's
# no shell-agnostic way to source a .env file before `streamlit run`
# starts. This is the actual entrypoint, so it's the right place to
# load .env into the process once, before anything calls get_settings().
load_dotenv(_PROJECT_ROOT / ".env")

import streamlit as st

from app.components.artifact_view import render_artifact
from app.components.chat import render_message, stream_words
from core.graph import run as run_turn
from core.state import AssistantState

# Stable default until real auth exists — profile facts persist across
# threads keyed by this, per core/state.py's user_id docstring.
_DEFAULT_USER_ID = "local-user"

st.set_page_config(page_title="Coding Assistant", page_icon="🧑‍💻", layout="wide")


def _init_session() -> None:
    """Set up per-session state on first load.

    thread_id/awaiting_feedback/awaiting_teaching/pending_question here
    are the app-layer's responsibility to carry across turns — see
    app/__init__.py's docstring for why core/ doesn't persist any of
    these itself.
    """
    st.session_state.setdefault("thread_id", str(uuid.uuid4()))
    st.session_state.setdefault("messages", [])  # list of {"role", "content", "artifacts"}
    st.session_state.setdefault("awaiting_feedback", False)
    st.session_state.setdefault("awaiting_teaching", False)
    st.session_state.setdefault("pending_question", None)


def _new_conversation() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.awaiting_feedback = False
    st.session_state.awaiting_teaching = False
    st.session_state.pending_question = None


_init_session()

with st.sidebar:
    st.header("Coding Assistant")
    if st.button("New conversation"):
        _new_conversation()
        st.rerun()

    st.divider()
    uploaded = st.file_uploader(
        "Attach a code file (optional)",
        type=["py", "js", "ts", "java", "go", "rb", "c", "cpp", "md", "txt"],
        help="Included with every message until you remove it here.",
    )
    attached_code = uploaded.getvalue().decode("utf-8", errors="replace") if uploaded is not None else None
    if attached_code is not None:
        st.caption(f"Attached: {uploaded.name} ({len(attached_code)} chars)")

for i, message in enumerate(st.session_state.messages):
    render_message(message["role"], message["content"], message["artifacts"], message_key=f"hist{i}")

prompt = st.chat_input("Ask a question or describe the code you want")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "artifacts": []})
    with st.chat_message("user"):
        st.markdown(prompt)
        if attached_code is not None:
            st.caption(f"(with attached file: {uploaded.name})")

    state = AssistantState(
        request_id=str(uuid.uuid4()),
        thread_id=st.session_state.thread_id,
        user_id=_DEFAULT_USER_ID,
        user_message=prompt,
        attached_code=attached_code,
        language=None,
        awaiting_feedback=st.session_state.awaiting_feedback,
        awaiting_teaching=st.session_state.awaiting_teaching,
        pending_question=st.session_state.pending_question,
    )

    with st.chat_message("assistant"):
        try:
            with st.spinner("Working…"):
                final_state = run_turn(state)
        except Exception as error:  # noqa: BLE001 — surface any failure in-chat, don't crash the app
            st.error(f"Something went wrong: {error}")
            st.session_state.messages.append(
                {"role": "assistant", "content": f"⚠️ {error}", "artifacts": []}
            )
        else:
            answer = final_state.answer or "(no answer produced)"
            st.write_stream(stream_words(answer))
            for i, artifact in enumerate(final_state.artifacts):
                render_artifact(artifact, key_prefix=f"new-{state.request_id}-{i}")

            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "artifacts": final_state.artifacts}
            )
            st.session_state.awaiting_feedback = final_state.awaiting_feedback
            st.session_state.awaiting_teaching = final_state.awaiting_teaching
            st.session_state.pending_question = final_state.pending_question
