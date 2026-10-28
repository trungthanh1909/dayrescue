"""Deterministic validation. No LLM or optimization dependency."""

from .models import (
    Activity,
    DayContext,
    ProposedPlan,
    ScheduledItem,
    ValidationIssue,
    ValidationResult,
)


def _overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Half-open intervals: touching endpoints do not count as overlapping."""
    return start_a < end_b and start_b < end_a


def detect_hard_conflicts(context: DayContext) -> list[ValidationIssue]:
    """Prove only simple contradictions among immutable, pending activities.

    This is NOT a general feasibility solver. Flexible activities may always
    be postponed, and a lack of detected conflicts doesn't prove optimality.
    """
    problems: list[ValidationIssue] = []
    fixed = [activity for activity in context.activities if activity.fixed]
    for activity in fixed:
        if activity.start_minute < context.now_minute:
            problems.append(ValidationIssue(
                code="FIXED_IN_PAST",
                message=f"Fixed activity {activity.id} starts before now.",
                activity_ids=[activity.id],
            ))
        if (activity.start_minute < context.day_start_minute
                or activity.end_minute > context.day_end_minute):
            problems.append(ValidationIssue(
                code="FIXED_OUT_OF_BOUNDS",
                message=f"Fixed activity {activity.id} is outside the day horizon.",
                activity_ids=[activity.id],
            ))
        for busy in context.busy_windows:
            if _overlap(activity.start_minute, activity.end_minute,
                        busy.start_minute, busy.end_minute):
                problems.append(ValidationIssue(
                    code="FIXED_BUSY_CONFLICT",
                    message=f"Fixed activity {activity.id} overlaps unavailable time: {busy.label}.",
                    activity_ids=[activity.id],
                ))
    for i, first in enumerate(fixed):
        for second in fixed[i + 1:]:
            if _overlap(first.start_minute, first.end_minute,
                        second.start_minute, second.end_minute):
                problems.append(ValidationIssue(
                    code="FIXED_FIXED_CONFLICT",
                    message=f"Fixed activities {first.id} and {second.id} overlap.",
                    activity_ids=[first.id, second.id],
                ))
    return problems


def validate_plan(context: DayContext, proposal: ProposedPlan) -> ValidationResult:
    """Verify hard constraints and classify proposed dispositions.

    Every original activity must occur exactly once as scheduled or postponed.
    Fixed activities cannot be changed or postponed. Flexible activities may
    change start time, but their duration is immutable unless a minimum is
    explicitly supplied. This function never re-plans or executes AI output.
    """
    issues = detect_hard_conflicts(context)
    original: dict[str, Activity] = {a.id: a for a in context.activities}
    seen_scheduled: dict[str, ScheduledItem] = {}
    seen_postponed: set[str] = set()

    for item in proposal.scheduled:
        activity = original.get(item.activity_id)
        if activity is None:
            issues.append(ValidationIssue(
                code="UNKNOWN_ACTIVITY", message=f"Unknown activity: {item.activity_id}.",
                activity_ids=[item.activity_id],
            ))
            continue
        if item.activity_id in seen_scheduled:
            issues.append(ValidationIssue(
                code="DUPLICATE_SCHEDULED", message=f"Activity {item.activity_id} scheduled twice.",
                activity_ids=[item.activity_id],
            ))
            continue
        seen_scheduled[item.activity_id] = item

        if item.start_minute < context.now_minute:
            issues.append(ValidationIssue(
                code="PAST_SCHEDULING", message=f"Activity {item.activity_id} starts before now.",
                activity_ids=[item.activity_id],
            ))
        if (item.start_minute < context.day_start_minute
                or item.end_minute > context.day_end_minute):
            issues.append(ValidationIssue(
                code="OUT_OF_BOUNDS", message=f"Activity {item.activity_id} is outside the day horizon.",
                activity_ids=[item.activity_id],
            ))
        if activity.fixed:
            if item.start_minute != activity.start_minute:
                issues.append(ValidationIssue(
                    code="FIXED_MOVED", message=f"Fixed activity {item.activity_id} was moved.",
                    activity_ids=[item.activity_id],
                ))
            if item.duration_minutes != activity.duration_minutes:
                issues.append(ValidationIssue(
                    code="FIXED_DURATION_CHANGED", message=f"Fixed activity {item.activity_id} changed duration.",
                    activity_ids=[item.activity_id],
                ))
        else:
            min_length = activity.min_duration_minutes or activity.duration_minutes
            if not min_length <= item.duration_minutes <= activity.duration_minutes:
                issues.append(ValidationIssue(
                    code="DURATION_NOT_ALLOWED",
                    message=f"Activity {item.activity_id} has a disallowed duration.",
                    activity_ids=[item.activity_id],
                ))
        for busy in context.busy_windows:
            if _overlap(item.start_minute, item.end_minute,
                        busy.start_minute, busy.end_minute):
                issues.append(ValidationIssue(
                    code="BUSY_OVERLAP",
                    message=f"Activity {item.activity_id} overlaps unavailable time: {busy.label}.",
                    activity_ids=[item.activity_id],
                ))

    for item_id in proposal.postponed_ids:
        activity = original.get(item_id)
        if activity is None:
            issues.append(ValidationIssue(
                code="UNKNOWN_POSTPONED", message=f"Unknown postponed activity: {item_id}.",
                activity_ids=[item_id],
            ))
        if item_id in seen_postponed:
            issues.append(ValidationIssue(
                code="DUPLICATE_POSTPONED", message=f"Activity {item_id} postponed twice.",
                activity_ids=[item_id],
            ))
        seen_postponed.add(item_id)
        if activity is not None and activity.fixed:
            issues.append(ValidationIssue(
                code="FIXED_POSTPONED", message=f"Fixed activity {item_id} cannot be postponed.",
                activity_ids=[item_id],
            ))
        if item_id in seen_scheduled:
            issues.append(ValidationIssue(
                code="DOUBLE_DISPOSITION", message=f"Activity {item_id} is scheduled and postponed.",
                activity_ids=[item_id],
            ))

    for activity in context.activities:
        if activity.id not in seen_scheduled and activity.id not in seen_postponed:
            issues.append(ValidationIssue(
                code="MISSING_ACTIVITY", message=f"Activity {activity.id} was omitted without postponement.",
                activity_ids=[activity.id],
            ))

    actual_items = list(seen_scheduled.values())
    for index, first in enumerate(actual_items):
        for second in actual_items[index + 1:]:
            if _overlap(first.start_minute, first.end_minute,
                        second.start_minute, second.end_minute):
                issues.append(ValidationIssue(
                    code="SCHEDULE_OVERLAP",
                    message=f"Activities {first.activity_id} and {second.activity_id} overlap.",
                    activity_ids=[first.activity_id, second.activity_id],
                ))

    kept = [a.id for a in context.activities
            if a.id in seen_scheduled
            and seen_scheduled[a.id].start_minute == a.start_minute
            and seen_scheduled[a.id].duration_minutes == a.duration_minutes]
    adjusted = [a.id for a in context.activities
                if a.id in seen_scheduled and a.id not in kept]
    postponed = [a.id for a in context.activities if a.id in seen_postponed]
    return ValidationResult(
        valid=not issues,
        issues=issues,
        kept_ids=kept,
        moved_or_adjusted_ids=adjusted,
        postponed_ids=postponed,
    )
