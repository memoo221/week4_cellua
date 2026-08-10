"""
app/components/artifact_view.py: render one Artifact with a "run" button.

Responsibility:
    Show a generated code block (syntax-highlighted via st.code) with a
    button that executes it through services.runner and displays the
    result inline. This is the one place the "execute generated code"
    requirement is wired up.

Allowed imports:
    - streamlit
    - core.types (Artifact)
    - services.runner (terminal_runner, protocol)
"""

from __future__ import annotations

import streamlit as st

from core.types import Artifact
from services.runner import terminal_runner

# Wall-clock budget for a single "run" click. Generated code is
# untrusted and unsandboxed (see services/runner/terminal_runner.py's
# docstring) — a hard timeout is the only thing standing between a
# runaway/infinite-loop generation and a hung UI.
_RUN_TIMEOUT_SECONDS = 10.0


def render_artifact(artifact: Artifact, key_prefix: str) -> None:
    """Render one artifact: its code, a run button, and any result.

    Args:
        artifact: the code block to render.
        key_prefix: unique per call site (see app/components/chat.py's
            render_message docstring) — Artifact.id is a hash of
            (language, code), so two different turns that generate
            identical code would otherwise collide on the same
            Streamlit widget key when both render in one script run.
    """
    if artifact.description:
        st.caption(artifact.description)
    st.code(artifact.code, language=artifact.language)

    if not terminal_runner.supports(artifact.language):
        st.caption(f"Running {artifact.language} code isn't supported yet.")
        return

    result_key = f"run_result_{key_prefix}_{artifact.id}"
    st.warning(
        "Runs directly on this machine, unsandboxed — only run code you've reviewed.",
        icon="⚠️",
    )
    if st.button("▶ Run", key=f"run_button_{key_prefix}_{artifact.id}"):
        with st.spinner("Running…"):
            st.session_state[result_key] = terminal_runner.run(artifact, timeout=_RUN_TIMEOUT_SECONDS)

    result = st.session_state.get(result_key)
    if result is None:
        return
    if result.timed_out:
        st.error(f"Timed out after {_RUN_TIMEOUT_SECONDS:.0f}s")
    elif result.exit_code != 0:
        st.error(f"Exited with code {result.exit_code}")
    else:
        st.success("Exited 0")
    if result.stdout:
        st.text("stdout:")
        st.code(result.stdout, language="text")
    if result.stderr:
        st.text("stderr:")
        st.code(result.stderr, language="text")
