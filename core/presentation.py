"""Pure preparation of agent results for display; never invokes a provider."""

from dataclasses import dataclass
from hashlib import sha256
import json

from pydantic import ValidationError

from .agent import AgentResult
from .models import DayContext, ProposedPlan
from .validator import detect_hard_conflicts, validate_plan

SAFE_CODES = frozenset("""
FIXED_IN_PAST FIXED_OUT_OF_BOUNDS FIXED_BUSY_CONFLICT FIXED_FIXED_CONFLICT
UNKNOWN_ACTIVITY DUPLICATE_SCHEDULED PAST_SCHEDULING OUT_OF_BOUNDS FIXED_MOVED
FIXED_DURATION_CHANGED DURATION_NOT_ALLOWED BUSY_OVERLAP UNKNOWN_POSTPONED
DUPLICATE_POSTPONED FIXED_POSTPONED DOUBLE_DISPOSITION MISSING_ACTIVITY
SCHEDULE_OVERLAP PROVIDER_ERROR MALFORMED_PROPOSAL
""".split())

MESSAGES = {
    "valid": "Agent result could not be verified for the current inputs. No plan is shown.",
    "infeasible": "Fixed-constraint conflicts prevent a valid plan with these immutable activities.",
    "invalid": "No valid proposal was found within two attempts. This does not prove the day is impossible.",
    "provider_error": "The proposal provider failed. No accepted plan is available.",
    "malformed_proposal": "The provider returned malformed proposal data. No accepted plan is available.",
}


@dataclass(frozen=True)
class AgentPresentation:
    status: str
    message: str
    validated: bool = False
    schedule: tuple[dict, ...] = ()
    dispositions: tuple[tuple[str, tuple[str, ...]], ...] = ()
    issues: tuple[str, ...] = ()
    trace: tuple[dict, ...] = ()
    rationale: str = ""


def input_fingerprint(context: DayContext, scope: str) -> str:
    content = json.dumps({"scope": scope, "context": context.model_dump(mode="json")}, sort_keys=True)
    return sha256(content.encode("utf-8")).hexdigest()


def _safe_codes(codes) -> str:
    return ", ".join(code if code in SAFE_CODES else "UNRECOGNIZED_CODE" for code in codes[:10])


def prepare_agent_result(context: DayContext, result: AgentResult) -> AgentPresentation:
    # Trace metadata is bounded and restricted to known labels/codes, never raw errors.
    trace = tuple({
        "Stage": event.stage if event.stage in ("preflight", "proposal") else "unknown",
        "Attempt": event.attempt if event.attempt in (0, 1, 2) else "unknown",
        "Outcome": event.outcome if event.outcome in ("clear", "infeasible", "valid", "invalid", "error") else "unknown",
        "Error codes": _safe_codes(event.error_codes),
    } for event in result.trace[:3])
    status = result.status if result.status in MESSAGES else "unknown"
    message = MESSAGES.get(status, "Unrecognized agent result. No plan is shown.")
    issues = ()
    if status == "infeasible":
        conflicts = detect_hard_conflicts(context)
        if conflicts:
            issues = tuple(f"{i.code}: {i.message}" for i in conflicts)
        else:
            message = "Reported fixed conflicts could not be confirmed for the current inputs. No plan is shown."
    elif status == "invalid" and result.validation and not result.validation.valid:
        # Do not render arbitrary issue messages, previous proposals or explanations.
        issues = tuple(dict.fromkeys(_safe_codes((i.code,)) for i in result.validation.issues))
    if status != "valid" or result.plan is None or result.validation is None or not result.validation.valid:
        return AgentPresentation(status, message, issues=issues, trace=trace)

    try:
        plan = ProposedPlan.model_validate_json(result.plan.model_dump_json(warnings=False))
    except (ValidationError, ValueError, TypeError):
        return AgentPresentation(status, message, trace=trace)
    validation = validate_plan(context, plan)
    if not validation.valid:
        return AgentPresentation(status, message, trace=trace)

    by_id = {a.id: a for a in context.activities}

    def clock(value):
        return f"{value // 60:02d}:{value % 60:02d}"

    schedule = tuple({
        "Activity": by_id[item.activity_id].title,
        "Start": clock(item.start_minute), "End": clock(item.end_minute),
        "Duration (min)": item.duration_minutes, "Priority": by_id[item.activity_id].priority,
        "Status": "Fixed" if by_id[item.activity_id].fixed else "Flexible",
    } for item in sorted(plan.scheduled, key=lambda item: item.start_minute))
    dispositions = tuple((label, tuple(f"{by_id[key].title} ({key})" for key in ids)) for label, ids in (
        ("Kept", validation.kept_ids), ("Moved / adjusted", validation.moved_or_adjusted_ids),
        ("Postponed", validation.postponed_ids),
    ))
    return AgentPresentation(status, "VALID — Python revalidated this proposal for the current inputs.",
                             True, schedule, dispositions, trace=trace,
                             rationale=plan.explanation[:1000])
