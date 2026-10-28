"""Offline validator preview, explicitly NOT a Meta AI demo."""

import streamlit as st

from core.scenarios import impossible_day, late_start, unexpected_event
from core.validator import detect_hard_conflicts, validate_plan


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


SCENARIOS = {
    "A · Late Start": late_start,
    "B · Unexpected Event": unexpected_event,
    "C · Impossible Day": impossible_day,
}

st.set_page_config(page_title="DayRescue", page_icon="🛟", layout="wide")
st.title("DayRescue")
st.caption("When Life Interrupts, Your Plan Adapts.")
st.warning(
    "OFFLINE VALIDATOR PREVIEW — proposals below are manually authored test "
    "fixtures, not Meta/Muse Spark AI output. Live API integration is blocked."
)

choice = st.selectbox("Choose a deterministic test scenario", list(SCENARIOS))
context, proposal = SCENARIOS[choice]()
result = validate_plan(context, proposal)

st.write(
    f"**Current time:** {clock(context.now_minute)} | "
    f"**Day horizon:** {clock(context.day_start_minute)}–{clock(context.day_end_minute)}"
)

left, right = st.columns(2)
with left:
    st.subheader("Original day")
    st.dataframe(
        [
            {
                "Activity": activity.title,
                "Start": clock(activity.start_minute),
                "End": clock(activity.end_minute),
                "Priority": activity.priority,
                "Fixed": "Yes" if activity.fixed else "No",
            }
            for activity in context.activities
        ],
        hide_index=True,
        use_container_width=True,
    )
    if context.busy_windows:
        st.write("**Unexpected busy time**")
        st.dataframe(
            [
                {"Label": busy.label, "Start": clock(busy.start_minute),
                 "End": clock(busy.end_minute)}
                for busy in context.busy_windows
            ],
            hide_index=True,
            use_container_width=True,
        )

with right:
    st.subheader("Hand-authored proposed plan")
    by_id = {activity.id: activity for activity in context.activities}
    st.dataframe(
        [
            {
                "Activity": by_id[item.activity_id].title,
                "Start": clock(item.start_minute),
                "End": clock(item.end_minute),
            }
            for item in sorted(proposal.scheduled, key=lambda item: item.start_minute)
            if item.activity_id in by_id
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.write("**Postponed:**", ", ".join(proposal.postponed_ids) or "None")

st.subheader("Python constraint validation")
if result.valid:
    st.success("VALID — this specific proposal satisfies declared hard constraints.")
else:
    st.error("INVALID — the backend rejects this proposal.")
    for problem in result.issues:
        st.write(f"- `{problem.code}`: {problem.message}")

hard_conflicts = detect_hard_conflicts(context)
if hard_conflicts:
    st.info(
        "Hard-conflict preflight found an immutable constraint contradiction. "
        "This is a narrow deterministic check, not a general feasibility solver."
    )

st.write(
    "**Verified disposition:** "
    f"kept={result.kept_ids}, "
    f"moved/adjusted={result.moved_or_adjusted_ids}, "
    f"postponed={result.postponed_ids}"
)
st.caption(
    "The real Muse Spark agent will generate proposed plans after Meta removes the "
    "account restriction. This preview never calls an AI model."
)
