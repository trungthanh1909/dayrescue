"""Offline demonstration fixtures (never shown as live Muse Spark output)."""

from .models import Activity, BusyWindow, DayContext, ProposedPlan, ScheduledItem


def late_start() -> tuple[DayContext, ProposedPlan]:
    context = DayContext(
        day_start_minute=7 * 60, day_end_minute=22 * 60, now_minute=9 * 60 + 30,
        activities=[
            Activity(id="reading", title="Morning reading", start_minute=8 * 60, duration_minutes=30, priority="low"),
            Activity(id="appointment", title="Doctor appointment", start_minute=10 * 60, duration_minutes=60, fixed=True, priority="high"),
            Activity(id="study", title="Study", start_minute=11 * 60, duration_minutes=90, priority="high"),
        ],
    )
    proposal = ProposedPlan(
        scheduled=[
            ScheduledItem(activity_id="appointment", start_minute=10 * 60, duration_minutes=60),
            ScheduledItem(activity_id="study", start_minute=11 * 60, duration_minutes=90),
        ],
        postponed_ids=["reading"],
        explanation="Offline hand-authored test fixture, NOT model output.",
    )
    return context, proposal


def unexpected_event() -> tuple[DayContext, ProposedPlan]:
    context = DayContext(
        day_start_minute=7 * 60, day_end_minute=22 * 60, now_minute=11 * 60,
        activities=[
            Activity(id="study", title="Study", start_minute=13 * 60, duration_minutes=90),
            Activity(id="call", title="Fixed call", start_minute=16 * 60, duration_minutes=30, fixed=True),
        ],
        busy_windows=[BusyWindow(start_minute=13 * 60, end_minute=15 * 60, label="Unexpected visitor")],
    )
    proposal = ProposedPlan(
        scheduled=[
            ScheduledItem(activity_id="study", start_minute=16 * 60 + 30, duration_minutes=90),
            ScheduledItem(activity_id="call", start_minute=16 * 60, duration_minutes=30),
        ],
        explanation="Offline hand-authored test fixture, NOT model output.",
    )
    return context, proposal


def impossible_day() -> tuple[DayContext, ProposedPlan]:
    context = DayContext(
        day_start_minute=7 * 60, day_end_minute=22 * 60, now_minute=12 * 60,
        activities=[
            Activity(id="meeting", title="Fixed meeting", start_minute=14 * 60, duration_minutes=60, fixed=True),
        ],
        busy_windows=[BusyWindow(start_minute=14 * 60 + 30, end_minute=15 * 60 + 30,
                                 label="Unavoidable family event")],
    )
    proposal = ProposedPlan(
        scheduled=[ScheduledItem(activity_id="meeting", start_minute=14 * 60, duration_minutes=60)],
        explanation="Offline hand-authored test fixture, NOT model output.",
    )
    return context, proposal
