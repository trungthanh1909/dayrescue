"""Render prepared results and bind session results to the current input."""

from collections.abc import MutableMapping
from dataclasses import dataclass

import streamlit as st

from core.agent import AgentResult
from core.models import DayContext
from core.presentation import input_fingerprint, prepare_agent_result

INPUT_KEY = "agent_input_fingerprint"
RESULT_KEY = "agent_result"


@dataclass(frozen=True)
class SavedAgentResult:
    fingerprint: str
    result: AgentResult


def store_agent_result(state: MutableMapping, context: DayContext, scope: str, result: AgentResult) -> bool:
    """Future invocation code may store only results for the currently displayed input."""
    fingerprint = input_fingerprint(context, scope)
    if state.get(INPUT_KEY) != fingerprint:
        return False
    state[RESULT_KEY] = SavedAgentResult(fingerprint, result)
    return True


def current_agent_result(state: MutableMapping, context: DayContext | None, scope: str) -> AgentResult | None:
    fingerprint = input_fingerprint(context, scope) if context is not None else None
    if fingerprint is None or state.get(INPUT_KEY) != fingerprint:
        state.pop(RESULT_KEY, None)
    state[INPUT_KEY] = fingerprint
    saved = state.get(RESULT_KEY)
    if (not isinstance(saved, SavedAgentResult) or saved.fingerprint != fingerprint
            or not isinstance(saved.result, AgentResult)):
        state.pop(RESULT_KEY, None)
        return None
    return saved.result


def render_agent_result(context: DayContext, result: AgentResult) -> None:
    view = prepare_agent_result(context, result)
    st.caption(f"Agent terminal status: {view.status}")
    if view.validated:
        st.success(view.message)
        st.subheader("Python-validated proposed schedule")
        if view.schedule:
            st.dataframe(list(view.schedule), hide_index=True, width="stretch")
        else:
            st.caption("No activities scheduled; see postponed activities below.")
        for label, names in view.dispositions:
            st.write(f"**{label}:** " + (", ".join(names) or "None"))
    else:
        st.error(view.message)
        st.caption("Validation outcome: no accepted plan for the current inputs.")
        for issue in view.issues:
            st.write(issue)
    with st.expander("Agent execution trace"):
        if view.trace:
            st.dataframe(list(view.trace), hide_index=True, width="stretch")
        st.caption("At most one preflight and two proposal attempts. Trace shows metadata only.")


def show_current_agent_result(context: DayContext | None, scope: str) -> None:
    result = current_agent_result(st.session_state, context, scope)
    st.subheader("Agent result")
    if result is not None:
        render_agent_result(context, result)
    else:
        st.caption("No agent result for these inputs. Live AI generation remains disabled.")
