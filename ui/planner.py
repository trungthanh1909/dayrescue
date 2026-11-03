"""Escaped, read-only planner presentation. Python remains the validity authority."""

from html import escape

import streamlit as st

from core.models import DayContext, ProposedPlan
from core.validator import validate_plan


PLANNER_CSS = """
<style>
.dr-plan {list-style:none;padding:0;margin:0 0 1.25rem;color:#243e48;font-family:inherit}
.dr-plan .dr-card {background:#fff;border:1px solid #d5e0e3;border-left:4px solid #b8b2d4;
  border-radius:6px 14px 14px 6px;padding:1rem 1.15rem;margin:.7rem 0;overflow-wrap:anywhere}
.dr-card.dr-fixed {border-left-color:#648f86}
.dr-card.dr-adjusted {background:#f6f4fb;border-left-color:#8476ae}
.dr-plan .dr-card .dr-title {display:block;font:600 1.05rem/1.5 "Trebuchet MS",sans-serif;margin:0;padding:0;color:#243e48}
.dr-top {display:flex;justify-content:space-between;align-items:start;gap:.7rem;flex-wrap:wrap}
.dr-badge {font:600 .8rem/1.5 sans-serif;padding:.15rem .5rem;border-radius:5px;
  color:#555078;background:#eeedf8}
.dr-fixed .dr-badge {color:#325e53;background:#e5efeb}
.dr-plan .dr-card .dr-meta {display:flex;flex-wrap:wrap;gap:.3rem 1rem;margin:.5rem 0 0;
  color:#536b74;font-size:.9rem;font-variant-numeric:tabular-nums}
.dr-plan .dr-card .dr-change {color:#555078;font-size:.9rem;margin:.65rem 0 0}
.dr-names {overflow-wrap:anywhere}
.dr-note {color:#000;font-size:.9rem;line-height:1.6;overflow-wrap:anywhere}
.dr-outcome {color:#243e48;background:#e3f0ea;border:1px solid #c5dcd2;
  border-radius:16px;padding:1.2rem 1.4rem;margin:1rem 0 1.4rem;overflow-wrap:anywhere}
.dr-outcome.dr-outcome h3 {font:600 1.25rem/1.5 "Trebuchet MS",sans-serif;margin:0;padding:0;color:#243e48}
.dr-outcome.dr-outcome p {margin:.6rem 0 0;line-height:1.6}
.dr-interruption {background:#fff1d8;color:#81521a;border-left:3px solid #b18138;
  border-radius:4px 12px 12px 4px;padding:1rem 1.2rem;margin:.7rem 0;overflow-wrap:anywhere}
.dr-interruption.dr-interruption p {margin:.4rem 0;line-height:1.6}
.dr-unscheduled {background:#fff7e9;border:1px dashed #b89a65;border-radius:12px;
  padding:1rem 1.2rem;color:#243e48;overflow-wrap:anywhere;margin:.7rem 0}
@media(max-width:640px) {.dr-plan .dr-card {padding:.9rem} .dr-plan .dr-card .dr-meta {font-size:.88rem;gap:.3rem .7rem}}
</style>
"""


def apply_planner_style():
    # Only our own classes; native widgets retain Streamlit's theme and focus states.
    st.markdown(PLANNER_CSS, unsafe_allow_html=True)


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def readable_caption(text):
    st.caption(f'<span class="dr-note">{escape(text)}</span>', unsafe_allow_html=True)


def _card(activity, start, duration, change="", adjusted=False):
    shortening = (f"May shorten to {activity.min_duration_minutes} min"
                  if activity.min_duration_minutes is not None and not activity.fixed
                  else "Shortening not allowed")
    classes = "dr-card" + (" dr-fixed" if activity.fixed else "") + (" dr-adjusted" if adjusted else "")
    return (
        f'<li class="{classes}"><div class="dr-top"><strong class="dr-title">{escape(activity.title)}</strong>'
        f'<span class="dr-badge">{"Fixed" if activity.fixed else "Flexible"}</span></div>'
        f'<p class="dr-meta"><span>{clock(start)}–{clock(start + duration)}</span>'
        f'<span>{duration} min</span><span>{escape(activity.priority.capitalize())} priority</span>'
        f'<span>{shortening}</span></p>'
        + (f'<p class="dr-change">{escape(change)}</p>' if change else "") + '</li>'
    )


def render_activity_cards(activities):
    st.markdown('<ol class="dr-plan" aria-label="Planned activities">' + "".join(
        _card(a, a.start_minute, a.duration_minutes)
        for a in sorted(activities, key=lambda a: a.start_minute)
    ) + '</ol>', unsafe_allow_html=True)


def original_tables(context):
    with st.expander("Original plan details", expanded=False):
        st.dataframe([
            {"ID": a.id, "Activity": a.title, "Start": clock(a.start_minute),
             "End": clock(a.end_minute), "Duration (min)": a.duration_minutes,
             "Priority": a.priority, "Status": "Fixed" if a.fixed else "Flexible",
             "Minimum duration (min)": a.min_duration_minutes}
            for a in sorted(context.activities, key=lambda a: a.start_minute)
        ], hide_index=True, width="stretch")
        if context.busy_windows:
            st.dataframe([
                {"Label": b.label, "Start": clock(b.start_minute), "End": clock(b.end_minute)}
                for b in context.busy_windows
            ], hide_index=True, width="stretch")


def render_original(context, title="Today's plan"):
    st.subheader(title)
    readable_caption(f"Current time {clock(context.now_minute)} · Day window "
                     f"{clock(context.day_start_minute)}–{clock(context.day_end_minute)} · Local times")
    render_activity_cards(context.activities)
    original_tables(context)


def render_interruptions(context):
    if not context.busy_windows:
        st.caption("No interruptions added. Your planned activities are unchanged.")
        return
    for busy in context.busy_windows:
        affected = [a for a in context.activities if busy.start_minute < a.end_minute
                    and a.start_minute < busy.end_minute]
        names = "; ".join(f"{a.title} ({'Fixed' if a.fixed else 'Flexible'})" for a in affected)
        feedback = ("Overlaps: " + names if affected else
                    "No activity overlaps detected. This is not proof of full feasibility.")
        st.markdown(
            f'<div class="dr-interruption"><strong>{escape(busy.label or "Unavailable time")}</strong>'
            f'<p>{clock(busy.start_minute)}–{clock(busy.end_minute)} · Unavoidable busy time</p>'
            f'<p>{escape(feedback)}</p></div>', unsafe_allow_html=True,
        )


def prepare_comparison(context: DayContext, proposal: ProposedPlan):
    """Detach and freshly validate before any revised card, summary or change is shown."""
    try:
        plan = ProposedPlan.model_validate_json(proposal.model_dump_json(warnings=False))
    except (ValueError, TypeError, AttributeError):
        return None
    validation = validate_plan(context, plan)
    if not validation.valid:
        return None
    return plan, validation


def render_outcome(validation, *, offline=False):
    counts = (f"{len(validation.kept_ids)} kept, "
              f"{len(validation.moved_or_adjusted_ids)} moved or adjusted, "
              f"{len(validation.postponed_ids)} postponed.")
    heading = "A hand-authored example to explore" if offline else "A revised day to review"
    st.markdown(
        f'<div class="dr-outcome"><h3>{heading}</h3><p>{counts}</p>'
        '<p>Review what changed and whether these tradeoffs work for you. '
        'This proposal is not a claim of an optimal schedule.</p></div>', unsafe_allow_html=True,
    )


def render_comparison(context, comparison, *, original_details=True):
    """Render only a freshly accepted comparison prepared above; no stored dispositions."""
    plan, validation = comparison
    by_id = {a.id: a for a in context.activities}
    left, right = st.columns(2)
    with left:
        st.subheader("Before · Original plan")
        render_activity_cards(context.activities)
        if original_details:
            original_tables(context)
    with right:
        st.subheader("After · Proposed plan")
        cards = []
        for item in sorted(plan.scheduled, key=lambda item: item.start_minute):
            activity = by_id[item.activity_id]
            changes = []
            if item.start_minute != activity.start_minute:
                changes.append(f"Moved from {clock(activity.start_minute)} to {clock(item.start_minute)}")
            if item.duration_minutes < activity.duration_minutes:
                changes.append(f"Shortened from {activity.duration_minutes} to {item.duration_minutes} min")
            cards.append(_card(activity, item.start_minute, item.duration_minutes,
                               "; ".join(changes) or "Kept at the same time and duration",
                               item.activity_id in validation.moved_or_adjusted_ids))
        if cards:
            st.markdown('<ol class="dr-plan" aria-label="Proposed activities">' + "".join(cards) + '</ol>', unsafe_allow_html=True)
        else:
            st.info("No activities scheduled in this proposal. Review the unscheduled items below.")
        with st.expander("Proposed plan details", expanded=False):
            st.dataframe([
                {"Activity": by_id[i.activity_id].title, "Start": clock(i.start_minute),
                 "End": clock(i.end_minute), "Duration (min)": i.duration_minutes,
                 "Priority": by_id[i.activity_id].priority,
                 "Status": "Fixed" if by_id[i.activity_id].fixed else "Flexible"}
                for i in sorted(plan.scheduled, key=lambda i: i.start_minute)
            ], hide_index=True, width="stretch")
    for label, ids in (("Kept", validation.kept_ids), ("Moved / adjusted", validation.moved_or_adjusted_ids),
                       ("Postponed", validation.postponed_ids)):
        # Keep untrusted activity names out of Markdown interpretation.
        st.markdown(f"**{label}:**")
        if ids:
            st.markdown(f'<p class="dr-names">{escape(", ".join(by_id[key].title for key in ids))}</p>', unsafe_allow_html=True)
        else:
            st.caption("None")
    st.markdown("#### Still unscheduled")
    if validation.postponed_ids:
        for key in validation.postponed_ids:
            activity = by_id[key]
            st.markdown(f'<div class="dr-unscheduled"><strong>{escape(activity.title)}</strong>'
                        f'<p>Postponed · Originally {clock(activity.start_minute)}–{clock(activity.end_minute)}. '
                        'Not assigned to another day.</p></div>', unsafe_allow_html=True)
    else:
        st.caption("None. Every activity is included in this proposed day.")
