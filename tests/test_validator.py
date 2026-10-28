"""Contract tests for the deterministic constraint checker (no API key)."""

import pytest
from pydantic import ValidationError

from core.models import Activity, BusyWindow, DayContext, ProposedPlan, ScheduledItem
from core.scenarios import impossible_day, late_start, unexpected_event
from core.validator import detect_hard_conflicts, validate_plan


def base_context(**overrides):
    params = dict(
        day_start_minute=7 * 60,
        day_end_minute=22 * 60,
        now_minute=8 * 60,
        activities=[
            Activity(id="flex", title="Flexible study", start_minute=10 * 60, duration_minutes=60),
            Activity(id="fixed", title="Fixed call", start_minute=12 * 60, duration_minutes=30, fixed=True),
        ],
    )
    return DayContext(**(params | overrides))


def valid_proposal():
    return ProposedPlan(scheduled=[
        ScheduledItem(activity_id="flex", start_minute=10 * 60, duration_minutes=60),
        ScheduledItem(activity_id="fixed", start_minute=12 * 60, duration_minutes=30),
    ])


def issue_codes(ctx, proposal):
    return {issue.code for issue in validate_plan(ctx, proposal).issues}


def test_valid_plan_is_accepted():
    result = validate_plan(base_context(), valid_proposal())
    assert result.valid
    assert result.kept_ids == ["flex", "fixed"]
    assert result.issues == []


def test_late_start_fixture_rescues_day():
    context, proposal = late_start()
    result = validate_plan(context, proposal)
    assert result.valid
    assert result.postponed_ids == ["reading"]


def test_unexpected_event_fixture_reschedules_flexible():
    context, proposal = unexpected_event()
    result = validate_plan(context, proposal)
    assert result.valid
    assert result.moved_or_adjusted_ids == ["study"]
    assert result.kept_ids == ["call"]


def test_impossible_day_detected_by_python():
    context, proposal = impossible_day()
    assert "FIXED_BUSY_CONFLICT" in {x.code for x in detect_hard_conflicts(context)}
    result = validate_plan(context, proposal)
    assert not result.valid
    assert "BUSY_OVERLAP" in {x.code for x in result.issues}


def test_fixed_start_cannot_move():
    proposal = valid_proposal()
    proposal.scheduled[1].start_minute = 13 * 60
    assert "FIXED_MOVED" in issue_codes(base_context(), proposal)


def test_fixed_duration_cannot_change():
    proposal = valid_proposal()
    proposal.scheduled[1].duration_minutes = 15
    assert "FIXED_DURATION_CHANGED" in issue_codes(base_context(), proposal)


def test_fixed_activity_cannot_be_postponed():
    proposal = ProposedPlan(
        scheduled=[ScheduledItem(activity_id="flex", start_minute=10 * 60, duration_minutes=60)],
        postponed_ids=["fixed"],
    )
    assert "FIXED_POSTPONED" in issue_codes(base_context(), proposal)


def test_flexible_duration_cannot_be_shortened_by_default():
    proposal = valid_proposal()
    proposal.scheduled[0].duration_minutes = 30
    assert "DURATION_NOT_ALLOWED" in issue_codes(base_context(), proposal)


def test_explicit_shortening_policy_is_enforced():
    context = base_context(activities=[
        Activity(id="flex", title="Flexible", start_minute=600, duration_minutes=60,
                 min_duration_minutes=30),
    ])
    valid = ProposedPlan(scheduled=[ScheduledItem(activity_id="flex", start_minute=600,
                                                  duration_minutes=30)])
    assert validate_plan(context, valid).valid
    invalid = ProposedPlan(scheduled=[ScheduledItem(activity_id="flex", start_minute=600,
                                                    duration_minutes=29)])
    assert "DURATION_NOT_ALLOWED" in issue_codes(context, invalid)


def test_unapproved_lengthening_is_invalid():
    proposal = valid_proposal()
    proposal.scheduled[0].duration_minutes = 90
    assert "DURATION_NOT_ALLOWED" in issue_codes(base_context(), proposal)


def test_missing_activity_must_be_marked_postponed():
    proposal = ProposedPlan(scheduled=[valid_proposal().scheduled[1]])
    assert "MISSING_ACTIVITY" in issue_codes(base_context(), proposal)


def test_unknown_scheduled_activity_is_rejected():
    proposal = valid_proposal()
    proposal.scheduled.append(ScheduledItem(activity_id="phantom", start_minute=800,
                                             duration_minutes=15))
    assert "UNKNOWN_ACTIVITY" in issue_codes(base_context(), proposal)


def test_unknown_postponed_activity_is_rejected():
    proposal = valid_proposal()
    proposal.postponed_ids = ["not-real"]
    assert "UNKNOWN_POSTPONED" in issue_codes(base_context(), proposal)


def test_duplicate_scheduled_activity_rejected():
    proposal = valid_proposal()
    proposal.scheduled.append(proposal.scheduled[0].model_copy(deep=True))
    assert "DUPLICATE_SCHEDULED" in issue_codes(base_context(), proposal)


def test_duplicate_postponed_activity_rejected():
    proposal = ProposedPlan(scheduled=[valid_proposal().scheduled[1]],
                            postponed_ids=["flex", "flex"])
    assert "DUPLICATE_POSTPONED" in issue_codes(base_context(), proposal)


def test_cannot_schedule_and_postpone_same_activity():
    proposal = valid_proposal()
    proposal.postponed_ids = ["flex"]
    assert "DOUBLE_DISPOSITION" in issue_codes(base_context(), proposal)


def test_scheduled_activities_cannot_overlap():
    proposal = valid_proposal()
    proposal.scheduled[0].start_minute = 11 * 60 + 30
    assert "SCHEDULE_OVERLAP" in issue_codes(base_context(), proposal)


def test_past_scheduling_rejected():
    proposal = valid_proposal()
    proposal.scheduled[0].start_minute = 7 * 60 + 30
    assert "PAST_SCHEDULING" in issue_codes(base_context(), proposal)


def test_scheduling_exactly_at_now_is_allowed():
    proposal = valid_proposal()
    proposal.scheduled[0].start_minute = 8 * 60
    assert validate_plan(base_context(), proposal).valid


def test_scheduling_outside_day_horizon_rejected():
    proposal = valid_proposal()
    proposal.scheduled[0].start_minute = 21 * 60 + 30
    assert "OUT_OF_BOUNDS" in issue_codes(base_context(), proposal)


def test_busy_window_overlap_rejected():
    context = base_context(busy_windows=[BusyWindow(start_minute=10 * 60 + 30,
                                                    end_minute=11 * 60 + 30)])
    assert "BUSY_OVERLAP" in issue_codes(context, valid_proposal())


def test_touching_busy_window_boundary_is_allowed():
    context = base_context(busy_windows=[BusyWindow(start_minute=11 * 60,
                                                    end_minute=11 * 60 + 30)])
    assert validate_plan(context, valid_proposal()).valid


def test_two_fixed_activities_conflict_is_provable():
    context = base_context(activities=[
        Activity(id="one", title="One", start_minute=600, duration_minutes=60, fixed=True),
        Activity(id="two", title="Two", start_minute=630, duration_minutes=60, fixed=True),
    ])
    assert "FIXED_FIXED_CONFLICT" in {x.code for x in detect_hard_conflicts(context)}


def test_fixed_activity_in_past_is_provably_infeasible():
    context = base_context(now_minute=13 * 60)
    assert "FIXED_IN_PAST" in {x.code for x in detect_hard_conflicts(context)}


def test_fixed_activity_outside_day_horizon_is_provable():
    context = base_context(day_end_minute=12 * 60 + 15)
    assert "FIXED_OUT_OF_BOUNDS" in {x.code for x in detect_hard_conflicts(context)}


def test_duplicate_original_ids_raise_validation_error():
    with pytest.raises(ValidationError, match="unique"):
        base_context(activities=[
            Activity(id="same", title="First", start_minute=600, duration_minutes=30),
            Activity(id="same", title="Second", start_minute=800, duration_minutes=30),
        ])


def test_invalid_busy_window_rejected_by_schema():
    with pytest.raises(ValidationError):
        BusyWindow(start_minute=900, end_minute=800)


def test_no_shorten_for_fixed_even_with_minimum():
    with pytest.raises(ValidationError):
        Activity(id="fix", title="Fixed", start_minute=600, duration_minutes=60,
                 fixed=True, min_duration_minutes=30)


def test_llm_cannot_supply_fake_validity_field():
    with pytest.raises(ValidationError):
        ProposedPlan.model_validate({
            "scheduled": [], "postponed_ids": [], "valid": True,
        })


def test_time_boundary_24h_is_not_valid_start():
    with pytest.raises(ValidationError):
        ScheduledItem(activity_id="x", start_minute=1440, duration_minutes=1)
