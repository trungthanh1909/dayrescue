"""Deterministic examples and explicitly enabled Custom day Muse Spark generation."""

from datetime import time

import streamlit as st
from pydantic import ValidationError

from core.scenarios import impossible_day, late_start, unexpected_event
from core.ui_input import build_day_context
from core.validator import detect_hard_conflicts, validate_plan
from ui.agent_result import invalidate_agent_result, show_current_agent_result
from ui.live_generation import show_live_generation
from ui.conflicts import show_conflicts
from ui.planner import (apply_planner_style, prepare_comparison, render_comparison,
                        render_interruptions, render_original, render_outcome, readable_caption)


SCENARIOS = {
    "A · Late Start": late_start,
    "B · Unexpected Event": unexpected_event,
    "C · Impossible Day": impossible_day,
}


def show_preflight(context):
    st.subheader("Can your fixed activities stay put?")
    conflicts = detect_hard_conflicts(context)
    if conflicts:
        st.error("Some fixed commitments conflict. Change one of these commitments before seeking a revised plan.")
        show_conflicts(context, conflicts)
    else:
        with st.expander("Fixed-constraint check details", expanded=False):
            st.info("No fixed-constraint conflicts detected.")
    readable_caption(
        "This checks fixed activities against current time, the day horizon, busy windows "
        "and other fixed activities. Absence of detected conflicts does not prove full "
        "feasibility or optimality. Flexible activities have not been replanned."
    )


def custom_day():
    plan_area = st.container()
    with st.expander("Edit planned activities", expanded=False):
        st.subheader("Planned activity details")
        readable_caption("Enter 3–8 pending activities. All times are local, within one day (00:00–23:59).")
        columns = st.columns(3)
        now = columns[0].time_input("Current time", time(8), step=60, on_change=invalidate_agent_result)
        start = columns[1].time_input("Day start", time(7), step=60, on_change=invalidate_agent_result)
        end = columns[2].time_input("Day end", time(22), step=60, on_change=invalidate_agent_result)
        count = st.number_input("Number of pending activities", min_value=3, max_value=8, value=3, on_change=invalidate_agent_result)
        activities = []
        for index in range(count):
            prefix = f"activity_{index + 1}"
            with st.container(border=True):
                st.markdown(f"#### Activity {index + 1}")
                title = st.text_input("Name", f"Activity {index + 1}", key=f"{prefix}_name", on_change=invalidate_agent_result)
                columns = st.columns(3)
                activity_start = columns[0].time_input("Start time", time(9 + index), step=60, key=f"{prefix}_start", on_change=invalidate_agent_result)
                duration = columns[1].number_input("Duration (minutes)", value=60, step=1, key=f"{prefix}_duration", on_change=invalidate_agent_result)
                priority = columns[2].selectbox("Priority", ["high", "medium", "low"], index=1, key=f"{prefix}_priority", on_change=invalidate_agent_result)
                fixed = st.checkbox("Fixed activity", key=f"{prefix}_fixed", help="Fixed activities must keep their original start and duration.", on_change=invalidate_agent_result)
                minimum = None
                if not fixed and st.checkbox("Allow shortening", key=f"{prefix}_shorten", on_change=invalidate_agent_result):
                    minimum = st.number_input("Minimum duration (minutes)", value=30, step=1, key=f"{prefix}_minimum", on_change=invalidate_agent_result)
                activities.append({"id": prefix, "title": title.strip(), "start_time": activity_start,
                                   "duration_minutes": duration, "priority": priority,
                                   "fixed": fixed, "min_duration_minutes": minimum})
    st.subheader("Something changed?")
    readable_caption("Add 0–10 interruptions. Each is unavoidable busy time that the revised plan must keep free.")
    busy_count = st.number_input("Number of unexpected busy windows", min_value=0, max_value=10, value=0, on_change=invalidate_agent_result)
    busy = []
    for index in range(busy_count):
        with st.expander(f"Interruption {index + 1}", expanded=True):
            label = st.text_input("Busy window label", "Unexpected event", key=f"busy_{index}_label", on_change=invalidate_agent_result)
            columns = st.columns(2)
            busy_start = columns[0].time_input("Busy start", time(13), step=60, key=f"busy_{index}_start", on_change=invalidate_agent_result)
            busy_end = columns[1].time_input("Busy end", time(14), step=60, key=f"busy_{index}_end", on_change=invalidate_agent_result)
            busy.append({"label": label, "start_time": busy_start, "end_time": busy_end})
    try:
        context = build_day_context(now=now, day_start=start, day_end=end,
                                    activities=activities, busy_windows=busy)
    except ValidationError as exc:
        show_current_agent_result(None, "custom")
        with plan_area:
            st.error("Please correct the input below. No constraint check has been run.")
        for error in exc.errors(include_input=False, include_url=False):
            location = " → ".join(str(part + 1) if isinstance(part, int) else part.replace("_", " ")
                                  for part in error["loc"]) or "Day context"
            st.write(f"**{location}**: {error['msg']}")
        return
    except ValueError as exc:
        show_current_agent_result(None, "custom")
        with plan_area:
            st.error(f"Please correct the time input: {exc}")
        return
    with plan_area:
        render_original(context)
    render_interruptions(context)
    show_preflight(context)
    show_live_generation(context, conflicts_shown=True)


st.set_page_config(page_title="DayRescue", page_icon="🛟", layout="wide")
apply_planner_style()
st.title("DayRescue")
readable_caption("A little room for real life. Plan your day, add what changed, then review the tradeoffs.")
mode = st.radio("Input mode", ["Example scenarios", "Custom day"], horizontal=True, on_change=invalidate_agent_result)
if mode == "Custom day":
    st.header("My day")
    readable_caption("Your inputs live in this session. No saved calendar or date-based planning is provided.")
    custom_day()
    st.stop()

st.header("Explore a sample day")
st.info("Explore hand-authored examples with deterministic Python checks. No AI generates these proposals.")
choice = st.selectbox("Choose a deterministic test scenario", list(SCENARIOS), on_change=invalidate_agent_result)
readable_caption("OFFLINE, HAND-AUTHORED FIXTURE — not Meta/Muse Spark model output.")
context, proposal = SCENARIOS[choice]()
result = validate_plan(context, proposal)
comparison = prepare_comparison(context, proposal)
if comparison is not None:
    render_outcome(comparison[1], offline=True)
    render_comparison(context, comparison)
else:
    st.error("INVALID — the backend rejects this hand-authored proposal. No revised schedule is shown.")
    left, right = st.columns(2)
    with left:
        render_original(context)
    with right:
        st.subheader("No accepted example plan")
        st.write("The fixed commitments and interruption cannot coexist. Review the conflicts below.")
st.subheader("Something changed?")
render_interruptions(context)
show_preflight(context)
with st.expander("Python constraint validation", expanded=False):
    if result.valid:
        st.success("VALID — this specific hand-authored proposal satisfies declared hard constraints.")
    else:
        for problem in result.issues:
            st.write(f"- `{problem.code}`: {problem.message}")
    st.write("**Verified disposition:** "
             f"kept={result.kept_ids}, moved/adjusted={result.moved_or_adjusted_ids}, "
             f"postponed={result.postponed_ids}")
readable_caption("Example proposals are hand-authored fixtures. Example mode never calls an AI model.")
st.button("Generate with Muse Spark", disabled=True)
show_current_agent_result(context, f"example:{choice}")
