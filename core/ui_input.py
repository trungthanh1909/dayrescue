"""Convert local UI values into existing domain contracts; no scheduling rules."""

from datetime import time

from pydantic import TypeAdapter

from .models import DayContext


def time_to_minutes(value: time | str) -> int:
    parsed = TypeAdapter(time).validate_python(value)
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ValueError("Use a local time with whole minutes (HH:MM).")
    return parsed.hour * 60 + parsed.minute


def build_day_context(*, now, day_start, day_end, activities, busy_windows) -> DayContext:
    """Rows use stable IDs, time-valued starts/ends and domain field names.

    Domain validation (including durations and unique IDs) stays in Pydantic.
    The UI controls its own 3–8 activity count; the domain still permits 1–8.
    """
    return DayContext.model_validate({
        "now_minute": time_to_minutes(now),
        "day_start_minute": time_to_minutes(day_start),
        "day_end_minute": time_to_minutes(day_end),
        "activities": [
            {**{key: value for key, value in row.items() if key != "start_time"},
             "start_minute": time_to_minutes(row["start_time"])}
            for row in activities
        ],
        "busy_windows": [
            {"label": row["label"],
             "start_minute": time_to_minutes(row["start_time"]),
             "end_minute": time_to_minutes(row["end_time"])}
            for row in busy_windows
        ],
    })
