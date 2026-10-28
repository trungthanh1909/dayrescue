from datetime import time

import pytest
from pydantic import ValidationError

from core.ui_input import build_day_context, time_to_minutes
from core.validator import detect_hard_conflicts


def custom_input():
    return dict(now=time(8), day_start=time(7), day_end=time(22), activities=[
        dict(id=f"activity_{i}", title=f"Task {i}", start_time=time(9 + i),
             duration_minutes=60, priority="high", fixed=False, min_duration_minutes=None)
        for i in range(3)
    ], busy_windows=[dict(label="Visitor", start_time=time(13), end_time=time(14))])


def test_custom_conversion_preserves_domain_values():
    data = custom_input()
    data["activities"][0]["min_duration_minutes"] = 30
    context = build_day_context(**data)
    assert (context.now_minute, context.day_start_minute, context.day_end_minute) == (480, 420, 1320)
    assert context.activities[0].start_minute == 540
    assert context.activities[0].min_duration_minutes == 30
    assert context.activities[0].priority == "high"
    assert context.busy_windows[0].end_minute == 840


@pytest.mark.parametrize("value", ["25:00", "bad", "09:30:01", time(9, 30, 0, 1), None])
def test_invalid_time_conversion(value):
    with pytest.raises((ValidationError, ValueError)):
        time_to_minutes(value)


def test_valid_minute_conversion():
    assert time_to_minutes("09:30") == 570
    assert time_to_minutes(time(23, 59)) == 1439


@pytest.mark.parametrize("duration", [0, -1, 1441, "invalid"])
def test_invalid_durations_use_domain_validation(duration):
    data = custom_input()
    data["activities"][0]["duration_minutes"] = duration
    with pytest.raises(ValidationError):
        build_day_context(**data)


@pytest.mark.parametrize("minimum", [0, 61])
def test_invalid_minimum_duration(minimum):
    data = custom_input()
    data["activities"][0]["min_duration_minutes"] = minimum
    with pytest.raises(ValidationError):
        build_day_context(**data)


def test_duplicate_ids_are_rejected_by_existing_model():
    data = custom_input()
    data["activities"][1]["id"] = "activity_0"
    with pytest.raises(ValidationError, match="unique"):
        build_day_context(**data)


@pytest.mark.parametrize("change", ["horizon", "now", "busy"])
def test_invalid_time_relationships(change):
    data = custom_input()
    if change == "horizon":
        data["day_end"] = time(6)
    elif change == "now":
        data["now"] = time(23)
    else:
        data["busy_windows"][0]["end_time"] = time(12)
    with pytest.raises(ValidationError):
        build_day_context(**data)


def test_converted_fixed_conflicts_are_detected():
    data = custom_input()
    for row in data["activities"][:2]:
        row.update(start_time=time(13), fixed=True)
    codes = {issue.code for issue in detect_hard_conflicts(build_day_context(**data))}
    assert codes == {"FIXED_FIXED_CONFLICT", "FIXED_BUSY_CONFLICT"}
