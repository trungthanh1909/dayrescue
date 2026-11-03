"""Render prepared results and bind session results to the current input."""

from collections.abc import MutableMapping
from dataclasses import dataclass

import streamlit as st

from core.agent import AgentResult
from core.models import DayContext
from core.validator import detect_hard_conflicts
from core.presentation import input_fingerprint, prepare_agent_result

from .conflicts import show_conflicts
from .planner import prepare_comparison, render_comparison, render_outcome, readable_caption

INPUT_KEY = "agent_input_fingerprint"
RESULT_KEY = "agent_result"


def invalidate_agent_result() -> None:
    """Widget callback: invalidate the binding before the next script rerun."""
    st.session_state.pop(RESULT_KEY, None)
    st.session_state[INPUT_KEY] = None


@dataclass(frozen=True)
class SavedAgentResult:
    fingerprint: str
    result: AgentResult


def store_agent_result(state: MutableMapping, context: DayContext, scope: str, result: AgentResult) -> bool:
    """Invocation code may store only results for the currently displayed input."""
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


def render_agent_result(context: DayContext, result: AgentResult, *, conflicts_shown: bool = False) -> None:
    view = prepare_agent_result(context, result)
    comparison = prepare_comparison(context, result.plan) if view.validated else None
    if view.validated and comparison is not None:
        render_outcome(comparison[1])
        readable_caption("Muse-generated proposal · Python checked the hard constraints for these inputs. Review the tradeoffs.")
        render_comparison(context, comparison, original_details=False)
        if view.rationale:
            with st.expander("Why this proposal? · Unverified AI rationale", expanded=False):
                st.subheader("AI-generated rationale (not independently verified)")
                st.text(view.rationale)
    else:
        st.error(view.message if not view.validated else
                 "The proposal could not be revalidated. No revised plan is shown.")
        readable_caption("Validation outcome: no accepted plan for the current inputs.")
        readable_caption("Your original activities remain above. Review the inputs before making another explicit request.")
        conflicts = detect_hard_conflicts(context) if view.status == "infeasible" else []
        if conflicts:
            if conflicts_shown:
                readable_caption("See the deterministic hard-conflict check above for counts, affected activities and full details.")
            else:
                show_conflicts(context, conflicts)
    with st.expander("Validation details", expanded=False):
        readable_caption(f"Agent terminal status: {view.status}")
        if view.validated and comparison is not None:
            st.success(view.message)
        else:
            for issue in view.issues:
                # Infeasible issues already have a complete grouped disclosure above.
                if view.status != "infeasible":
                    st.write(issue)
    with st.expander("Agent execution trace"):
        if view.trace:
            st.dataframe(list(view.trace), hide_index=True, width="stretch")
        readable_caption("At most one preflight and two proposal attempts. Trace shows metadata only.")


def show_current_agent_result(context: DayContext | None, scope: str, *, conflicts_shown: bool = False) -> None:
    result = current_agent_result(st.session_state, context, scope)
    st.subheader("Your rescued day")
    if result is not None:
        render_agent_result(context, result, conflicts_shown=conflicts_shown)
    else:
        readable_caption("No agent result for these inputs.")
