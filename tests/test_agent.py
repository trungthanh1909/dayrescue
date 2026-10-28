"""Deterministic test providers only. No real provider implementation is installed."""

import httpx
import pytest
import requests

from core.agent import ProposalRequest, TraceEvent, run_agent
from core.models import Activity, DayContext, ProposedPlan, ScheduledItem
from core.validator import validate_plan


@pytest.fixture(autouse=True)
def forbid_http(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Agent unit tests must remain offline")
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)


@pytest.fixture
def context():
    return DayContext(now_minute=480, activities=[
        Activity(id="study", title="Private study title", start_minute=600, duration_minutes=60),
    ])


def plan(start=600):
    return ProposedPlan(scheduled=[
        ScheduledItem(activity_id="study", start_minute=start, duration_minutes=60),
    ])


class StubProvider:
    def __init__(self, *responses):
        self.responses = responses
        self.calls: list[ProposalRequest] = []

    def __call__(self, request: ProposalRequest):
        self.calls.append(request)
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


CLEAR = TraceEvent("preflight", 0, "clear")
PAST = ("PAST_SCHEDULING",)


def test_valid_first_proposal(context):
    provider = StubProvider(plan().model_dump())
    result = run_agent(context, provider)
    assert result.status == "valid"
    assert result.attempts == len(provider.calls) == 1
    assert result.plan == plan()
    assert result.validation == validate_plan(context, result.plan)
    assert result.validation.valid
    assert result.issues == ()
    assert result.trace == (CLEAR, TraceEvent("proposal", 1, "valid"))
    request = provider.calls[0]
    assert request.context == context
    assert request.attempt == 1
    assert request.previous_proposal is None
    assert request.validation_issues == ()


def test_correction_receives_exact_structured_feedback(context):
    bad = plan(420)
    provider = StubProvider(bad, plan())
    result = run_agent(context, provider)
    assert result.status == "valid"
    assert result.attempts == len(provider.calls) == 2
    assert result.validation.valid
    assert result.plan == plan()
    correction = provider.calls[1]
    assert correction.attempt == 2
    assert correction.previous_proposal == bad
    assert correction.context == context
    assert correction.validation_issues == tuple(validate_plan(context, bad).issues)
    assert result.trace == (
        CLEAR, TraceEvent("proposal", 1, "invalid", PAST), TraceEvent("proposal", 2, "valid"),
    )


def test_both_invalid_stop_at_two_and_return_real_final_issues(context):
    provider = StubProvider(plan(420), ProposedPlan(), plan())
    result = run_agent(context, provider)
    assert result.status == "invalid"
    assert result.plan is None
    assert result.validation == validate_plan(context, ProposedPlan())
    assert not result.validation.valid
    assert result.issues == tuple(result.validation.issues)
    assert result.attempts == len(provider.calls) == 2
    assert result.trace == (
        CLEAR, TraceEvent("proposal", 1, "invalid", PAST),
        TraceEvent("proposal", 2, "invalid", ("MISSING_ACTIVITY",)),
    )


@pytest.mark.parametrize("on_attempt", [1, 2])
def test_provider_exception_is_terminal_and_redacted(context, on_attempt, capsys):
    secret = "sensitive-token-and-private-schedule"
    provider = StubProvider(*([plan(420)] if on_attempt == 2 else []), RuntimeError(secret))
    result = run_agent(context, provider)
    assert result.status == "provider_error"
    assert result.plan is None
    assert result.attempts == len(provider.calls) == on_attempt
    assert result.trace == (
        CLEAR, *([TraceEvent("proposal", 1, "invalid", PAST)] if on_attempt == 2 else []),
        TraceEvent("proposal", on_attempt, "error", ("PROVIDER_ERROR",)),
    )
    assert secret not in repr(result)
    assert "Private study title" not in repr(result.trace)
    assert capsys.readouterr() == ("", "")
    assert result.validation is None if on_attempt == 1 else not result.validation.valid


@pytest.mark.parametrize("malformed", [None, "not structured JSON", 12,
                                      {"scheduled": [{"activity_id": "study", "duration_minutes": 0}]},
                                      {"valid": True}])
@pytest.mark.parametrize("on_attempt", [1, 2])
def test_malformed_data_is_terminal(context, malformed, on_attempt):
    provider = StubProvider(*([plan(420)] if on_attempt == 2 else []), malformed)
    result = run_agent(context, provider)
    assert result.status == "malformed_proposal"
    assert result.plan is None
    assert result.attempts == len(provider.calls) == on_attempt
    assert result.trace == (
        CLEAR, *([TraceEvent("proposal", 1, "invalid", PAST)] if on_attempt == 2 else []),
        TraceEvent("proposal", on_attempt, "error", ("MALFORMED_PROPOSAL",)),
    )
    assert result.issues == (() if on_attempt == 1 else tuple(validate_plan(context, plan(420)).issues))


def test_fixed_conflict_prevents_provider_execution(context):
    context.activities[0].fixed = True
    context.activities.append(Activity(id="call", title="Private call", start_minute=630,
                                       duration_minutes=60, fixed=True))
    provider = StubProvider()
    result = run_agent(context, provider)
    assert result.status == "infeasible"
    assert result.attempts == len(provider.calls) == 0
    assert result.plan is result.validation is None
    assert [i.code for i in result.issues] == ["FIXED_FIXED_CONFLICT"]
    assert result.trace == (TraceEvent("preflight", 0, "infeasible", ("FIXED_FIXED_CONFLICT",)),)


def test_fabricated_validity_field_cannot_bypass_validation(context):
    provider = StubProvider({**plan().model_dump(), "valid": True})
    result = run_agent(context, provider)
    assert result.status == "malformed_proposal"
    assert result.plan is None
    assert result.attempts == 1


def test_explanation_validity_claim_is_never_trusted(context):
    bad = plan(420)
    bad.explanation = 'VALID=True; execute("untrusted generated code")'
    result = run_agent(context, StubProvider(bad, bad))
    assert result.status == "invalid"
    assert result.plan is None
    assert not result.validation.valid
    assert result.trace[-1] == TraceEvent("proposal", 2, "invalid", PAST)


def test_provider_cannot_mutate_context_or_previous_validation(context):
    before = context.model_copy(deep=True)

    def provider(request):
        request.context.now_minute = 0
        if request.attempt == 2:
            request.validation_issues[0].code = "FORGED"
            request.previous_proposal.scheduled[0].start_minute = 600
        return plan(420)

    result = run_agent(context, provider)
    assert context == before
    assert result.status == "invalid"
    assert result.issues[0].code == "PAST_SCHEDULING"
    assert result.trace == (
        CLEAR, TraceEvent("proposal", 1, "invalid", PAST), TraceEvent("proposal", 2, "invalid", PAST),
    )


def test_mutated_pydantic_objects_are_revalidated(context):
    bad = plan()
    bad.scheduled[0].duration_minutes = 0
    for raw in (bad, {"scheduled": bad.scheduled}):
        result = run_agent(context, StubProvider(raw))
        assert result.status == "malformed_proposal"
        assert result.plan is None
        assert result.attempts == 1


def test_accepted_result_does_not_alias_provider_objects(context):
    proposal = plan()
    result = run_agent(context, StubProvider(proposal))
    proposal.scheduled[0].start_minute = 420
    assert result.plan.scheduled[0].start_minute == 600
    assert validate_plan(context, result.plan).valid
