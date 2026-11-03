"""Custom-day click handler; no background invocation or cached generation."""

import streamlit as st

from core.live_generation import generate_live_result, live_ai_enabled
from core.models import DayContext
from .planner import readable_caption
from .agent_result import (
    RESULT_KEY, current_agent_result, show_current_agent_result, store_agent_result,
)


def show_live_generation(context: DayContext, *, conflicts_shown: bool = False) -> None:
    current_agent_result(st.session_state, context, "custom")
    enabled = live_ai_enabled()
    st.subheader("Rescue your day")
    if enabled:
        readable_caption("Generate a proposal for this day. Python checks its hard constraints; review the tradeoffs.")
    else:
        readable_caption("Live AI generation is disabled for this session.")
    readable_caption("Request a revised plan, then compare the changes. Nothing is saved to a calendar.")
    clicked = st.button("Generate with Muse Spark", disabled=not enabled, key="generate_live_ai", type="primary")
    if clicked and live_ai_enabled():
        snapshot = context.model_copy(deep=True)
        st.session_state.pop(RESULT_KEY, None)
        with st.spinner("Generating and checking your schedule…"):
            result = generate_live_result(snapshot)
        if not store_agent_result(st.session_state, snapshot, "custom", result):
            st.info("Inputs changed during generation. Generate again for the current day.")
            return
    show_current_agent_result(context, "custom", conflicts_shown=conflicts_shown)
