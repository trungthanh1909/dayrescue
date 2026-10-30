"""Deterministic examples and explicitly enabled Custom day Muse Spark generation."""

from datetime import time

import streamlit as st
from pydantic import ValidationError

from core.scenarios import impossible_day, late_start, unexpected_event
from core.ui_input import build_day_context
from core.validator import detect_hard_conflicts, validate_plan
from ui.agent_result import invalidate_agent_result, show_current_agent_result
from ui.live_generation import show_live_generation


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


SCENARIOS = {
    "A · Late Start": late_start,
    "B · Unexpected Event": unexpected_event,
    "C · Impossible Day": impossible_day,
}


def show_original(context):
    st.subheader("Original day")
    st.write(
        f"**Current time:** {clock(context.now_minute)} | "
        f"**Day horizon:** {clock(context.day_start_minute)}–{clock(context.day_end_minute)}"
    )
    st.dataframe([
        {"ID": a.id, "Activity": a.title, "Start": clock(a.start_minute),
         "End": clock(a.end_minute), "Duration (min)": a.duration_minutes,
         "Priority": a.priority, "Status": "Fixed" if a.fixed else "Flexible",
         "Minimum duration (min)": a.min_duration_minutes}
        for a in context.activities
    ], hide_index=True, width="stretch")
    st.write("**Unexpected busy windows**")
    if context.busy_windows:
        st.dataframe([
            {"Label": b.label, "Start": clock(b.start_minute), "End": clock(b.end_minute)}
            for b in context.busy_windows
        ], hide_index=True, width="stretch")
    else:
        st.caption("No unexpected busy windows.")


def show_preflight(context):
    st.subheader("Deterministic hard-conflict check")
    conflicts = detect_hard_conflicts(context)
    if conflicts:
        st.error("Hard conflicts detected in immutable activities.")
        names = {a.id: a.title for a in context.activities}
        for issue in conflicts:
            st.write(f"**{issue.code}**: {issue.message}")
            st.caption("Activities: " + ", ".join(names[item] for item in issue.activity_ids))
    else:
        st.info("No fixed-constraint conflicts detected.")
    st.caption(
        "This checks fixed activities against current time, the day horizon, busy windows "
        "and other fixed activities. Absence of detected conflicts does not prove full "
        "feasibility or optimality. Flexible activities have not been replanned."
    )


def custom_day():
    st.subheader("Create a custom day")
    st.caption("Enter 3–8 pending activities. All times are local, within one day (00:00–23:59).")
    columns = st.columns(3)
    now = columns[0].time_input("Current time", time(8), step=60, on_change=invalidate_agent_result)
    start = columns[1].time_input("Day start", time(7), step=60, on_change=invalidate_agent_result)
    end = columns[2].time_input("Day end", time(22), step=60, on_change=invalidate_agent_result)
    count = st.number_input("Number of pending activities", min_value=3, max_value=8, value=3, on_change=invalidate_agent_result)
    activities = []
    for index in range(count):
        prefix = f"activity_{index + 1}"
        with st.expander(f"Activity {index + 1}", expanded=True):
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
    busy_count = st.number_input("Number of unexpected busy windows", min_value=0, max_value=10, value=0, on_change=invalidate_agent_result)
    busy = []
    for index in range(busy_count):
        with st.expander(f"Busy window {index + 1}", expanded=True):
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
        st.error("Please correct the input below. No constraint check has been run.")
        for error in exc.errors(include_input=False, include_url=False):
            location = " → ".join(str(part + 1) if isinstance(part, int) else part.replace("_", " ")
                                  for part in error["loc"]) or "Day context"
            st.write(f"**{location}**: {error['msg']}")
        return
    except ValueError as exc:
        show_current_agent_result(None, "custom")
        st.error(f"Please correct the time input: {exc}")
        return
    show_original(context)
    show_preflight(context)
    show_live_generation(context)


st.set_page_config(page_title="DayRescue", page_icon="🛟", layout="wide")
st.title("DayRescue")
st.caption("When Life Interrupts, Your Plan Adapts.")
mode = st.radio("Input mode", ["Example scenarios", "Custom day"], horizontal=True, on_change=invalidate_agent_result)
if mode == "Custom day":
    custom_day()
    st.stop()

st.info("Examples use deterministic Python checks and hand-authored proposals. Live generation is available only in Custom day when enabled.")
st.button("Generate with Muse Spark", disabled=True)
choice = st.selectbox("Choose a deterministic test scenario", list(SCENARIOS), on_change=invalidate_agent_result)
st.caption("OFFLINE, HAND-AUTHORED FIXTURE — not Meta/Muse Spark model output.")
context, proposal = SCENARIOS[choice]()
result = validate_plan(context, proposal)

left, right = st.columns(2)
with left:
    show_original(context)

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
        width="stretch",
    )
    st.write("**Postponed:**", ", ".join(proposal.postponed_ids) or "None")

st.subheader("Python constraint validation")
if result.valid:
    st.success("VALID — this specific proposal satisfies declared hard constraints.")
else:
    st.error("INVALID — the backend rejects this proposal.")
    for problem in result.issues:
        st.write(f"- `{problem.code}`: {problem.message}")

show_preflight(context)

st.write(
    "**Verified disposition:** "
    f"kept={result.kept_ids}, "
    f"moved/adjusted={result.moved_or_adjusted_ids}, "
    f"postponed={result.postponed_ids}"
)
st.caption(
    "These example proposals are hand-authored fixtures. Example mode never calls an AI model."
)
show_current_agent_result(context, f"example:{choice}")
