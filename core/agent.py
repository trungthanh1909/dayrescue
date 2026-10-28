"""Bounded, provider-independent orchestration. No API client or fallback plans."""

from dataclasses import dataclass
from typing import Literal, Protocol

from .models import DayContext, ProposedPlan, ValidationIssue, ValidationResult
from .validator import detect_hard_conflicts, validate_plan


@dataclass(frozen=True)
class ProposalRequest:
    context: DayContext
    attempt: int
    previous_proposal: ProposedPlan | None = None
    validation_issues: tuple[ValidationIssue, ...] = ()


class ProposalProvider(Protocol):
    def __call__(self, request: ProposalRequest) -> ProposedPlan | dict[str, object]:
        """Return structured data; do not retry internally. Attempt is 1 or 2."""
        ...


@dataclass(frozen=True)
class TraceEvent:
    stage: Literal["preflight", "proposal"]
    attempt: int  # 0 for preflight; 1 or 2 counts actual provider invocations.
    outcome: Literal["clear", "infeasible", "valid", "invalid", "error"]
    error_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentResult:
    status: Literal["valid", "infeasible", "invalid", "provider_error", "malformed_proposal"]
    trace: tuple[TraceEvent, ...]
    # Only expose a plan when Python has accepted it.
    plan: ProposedPlan | None = None
    validation: ValidationResult | None = None  # Last completed validation, if any.
    hard_conflicts: tuple[ValidationIssue, ...] = ()

    @property
    def attempts(self) -> int:
        return sum(event.stage == "proposal" for event in self.trace)

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(self.validation.issues) if self.validation else self.hard_conflicts


def run_agent(context: DayContext, provider: ProposalProvider) -> AgentResult:
    """Preflight, then at most one initial proposal and one correction.

    Malformed data or provider exceptions terminate immediately, without retry.
    `invalid` means two schema-valid proposals failed deterministic validation;
    it is not a proof of infeasibility. Error traces contain codes only.
    """
    context = context.model_copy(deep=True)
    conflicts = tuple(detect_hard_conflicts(context))
    if conflicts:
        return AgentResult(
            status="infeasible", hard_conflicts=conflicts,
            trace=(TraceEvent("preflight", 0, "infeasible", tuple(i.code for i in conflicts)),),
        )

    trace = [TraceEvent("preflight", 0, "clear")]
    proposal = None
    validation = None
    for attempt in (1, 2):
        request = ProposalRequest(
            context=context.model_copy(deep=True), attempt=attempt,
            previous_proposal=proposal.model_copy(deep=True) if proposal else None,
            validation_issues=tuple(i.model_copy(deep=True) for i in validation.issues)
            if validation else (),
        )
        try:
            raw = provider(request)
        except Exception:
            # Provider errors can contain credentials, HTTP bodies or schedule data.
            trace.append(TraceEvent("proposal", attempt, "error", ("PROVIDER_ERROR",)))
            return AgentResult("provider_error", tuple(trace), validation=validation)

        try:
            parsed = ProposedPlan.model_validate(raw)
            # Revalidate mutable/model_construct instances, including nested items.
            # JSON round-trip also detaches provider-owned objects from the result.
            proposal = ProposedPlan.model_validate_json(parsed.model_dump_json(warnings=False))
        except (ValueError, TypeError):
            trace.append(TraceEvent("proposal", attempt, "error", ("MALFORMED_PROPOSAL",)))
            return AgentResult("malformed_proposal", tuple(trace), validation=validation)

        validation = validate_plan(context, proposal)
        trace.append(TraceEvent(
            "proposal", attempt, "valid" if validation.valid else "invalid",
            tuple(issue.code for issue in validation.issues),
        ))
        if validation.valid:
            return AgentResult("valid", tuple(trace), plan=proposal, validation=validation)

    return AgentResult("invalid", tuple(trace), validation=validation)
