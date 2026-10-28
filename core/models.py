"""Typed, deterministic contracts for a single day's *pending* activities.

All time values are integer minutes since local midnight, using half-open
intervals [start_minute, end_minute). No timezone or date calculations occur.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Activity(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=120)
    start_minute: int = Field(ge=0, lt=1440)
    duration_minutes: int = Field(gt=0, le=1440)
    priority: Literal["high", "medium", "low"] = "medium"
    fixed: bool = False
    # None means shortening is forbidden. If set, duration may decrease only
    # to this explicit minimum; fixed activities cannot change regardless.
    min_duration_minutes: int | None = Field(default=None, gt=0, le=1440)

    @model_validator(mode="after")
    def check_shortening_policy(self) -> "Activity":
        if self.min_duration_minutes is not None:
            if self.fixed:
                raise ValueError("fixed activities cannot allow shortening")
            if self.min_duration_minutes > self.duration_minutes:
                raise ValueError("min_duration_minutes exceeds original duration")
        return self

    @property
    def end_minute(self) -> int:
        return self.start_minute + self.duration_minutes


class BusyWindow(StrictModel):
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(gt=0, le=1440)
    label: str = Field(default="Unavailable", max_length=120)

    @model_validator(mode="after")
    def check_window(self) -> "BusyWindow":
        if self.end_minute <= self.start_minute:
            raise ValueError("busy window end must be later than start")
        return self


class DayContext(StrictModel):
    day_start_minute: int = Field(default=0, ge=0, lt=1440)
    day_end_minute: int = Field(default=1440, gt=0, le=1440)
    now_minute: int = Field(ge=0, le=1440)
    activities: list[Activity] = Field(min_length=1, max_length=8)
    busy_windows: list[BusyWindow] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def check_context(self) -> "DayContext":
        if self.day_end_minute <= self.day_start_minute:
            raise ValueError("day end must be after day start")
        if self.now_minute > self.day_end_minute:
            raise ValueError("now must not be after the day's horizon")
        ids = [activity.id for activity in self.activities]
        if len(set(ids)) != len(ids):
            raise ValueError("activity ids must be unique")
        return self


class ScheduledItem(StrictModel):
    activity_id: str = Field(min_length=1)
    start_minute: int = Field(ge=0, lt=1440)
    duration_minutes: int = Field(gt=0, le=1440)

    @property
    def end_minute(self) -> int:
        return self.start_minute + self.duration_minutes


class ProposedPlan(StrictModel):
    scheduled: list[ScheduledItem] = Field(default_factory=list, max_length=20)
    postponed_ids: list[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(default="", max_length=2000)


class ValidationIssue(StrictModel):
    code: str
    message: str
    activity_ids: list[str] = Field(default_factory=list)


class ValidationResult(StrictModel):
    # This property is always produced by Python validation, never trusted
    # from model output or ProposedPlan.explanation.
    valid: bool
    issues: list[ValidationIssue]
    kept_ids: list[str]
    moved_or_adjusted_ids: list[str]
    postponed_ids: list[str]
