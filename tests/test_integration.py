"""Full offline pipeline with real SDK + MockTransport, never live Muse output."""

from datetime import time
import json
import math
from pathlib import Path
import socket

import httpx
import pytest
import requests
from streamlit.testing.v1 import AppTest

from core.agent import run_agent
from core.meta_client import MetaProvider
from core.models import BusyWindow, ProposedPlan
from core.presentation import prepare_agent_result
from core.scenarios import impossible_day, late_start, unexpected_event
from core.ui_input import build_day_context
from core.validator import validate_plan
from ui.agent_result import RESULT_KEY, current_agent_result, store_agent_result

TEST_KEY = "offline-integration-test-key"
APP = Path(__file__).resolve().parents[1] / "app.py"
HARNESS = """
import streamlit as st
from ui.agent_result import show_current_agent_result
st.caption('TEST ONLY: MockTransport fixtures, not live Muse output.')
show_current_agent_result(st.session_state['context'], 'integration')
"""


@pytest.fixture(autouse=True)
def forbid_external_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Only in-memory MockTransport is permitted")
    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        # Windows asyncio wakeup socketpair; HTTP remains blocked even on localhost.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        blocked()

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL", raising=False)


def converted_scenario(scenario):
    """Round-trip the existing fixture through the actual UI conversion boundary.

    B/C retain the domain's minimal 2/1 activity fixtures; custom UI's 3–8 gate
    remains covered by AppTest. No extra demo activities are invented here.
    """
    original, proposal = scenario()

    def local_time(minutes):
        return time(minutes // 60, minutes % 60)

    rows = []
    for activity in original.activities:
        row = activity.model_dump(exclude={"start_minute"})
        row["start_time"] = local_time(activity.start_minute)
        rows.append(row)
    context = build_day_context(
        now=local_time(original.now_minute), day_start=local_time(original.day_start_minute),
        day_end=local_time(original.day_end_minute), activities=rows,
        busy_windows=[{"label": busy.label, "start_time": local_time(busy.start_minute),
                       "end_time": local_time(busy.end_minute)} for busy in original.busy_windows],
    )
    assert context == original
    return context, proposal


@pytest.fixture
def mock_provider():
    providers = []

    def make(*responses):
        calls = []

        def handler(request):
            calls.append(request)
            assert len(calls) <= 2
            assert len(calls) <= len(responses), "Unexpected extra SDK/agent request"
            assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
            timeouts = request.extensions["timeout"]
            assert timeouts["connect"] == 5.0
            assert all(math.isfinite(value) and 0 < value <= 30 for value in timeouts.values())
            body = json.loads(request.content)
            assert body["max_completion_tokens"] == 2048
            assert body["stream"] is False
            response = responses[len(calls) - 1]
            if callable(response):
                return response(request)
            if isinstance(response, httpx.Response):
                return response
            content = response.model_dump_json() if isinstance(response, ProposedPlan) else response
            return httpx.Response(200, json={
                "id": "offline-fixture", "object": "chat.completion", "created": 0,
                "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content}}],
            })

        provider = MetaProvider(api_key=TEST_KEY,
                                http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        providers.append(provider)
        assert provider._client.max_retries == 0
        assert calls == []
        return provider, calls

    yield make
    for provider in providers:
        provider.close()


def render_pipeline_result(context, result):
    state = {}
    current_agent_result(state, context, "integration")
    assert store_agent_result(state, context, "integration", result)
    app = AppTest.from_string(HARNESS)
    app.session_state["context"] = context
    for key, value in state.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    return app


@pytest.mark.parametrize("scenario,expected_status,request_count", [
    (late_start, "valid", 1), (unexpected_event, "valid", 1), (impossible_day, "infeasible", 0),
], ids=["late-start", "unexpected-event", "impossible-day"])
def test_demo_pipeline(scenario, expected_status, request_count, mock_provider):
    context, manual_proposal = converted_scenario(scenario)
    provider, calls = mock_provider(manual_proposal)
    result = run_agent(context, provider)
    view = prepare_agent_result(context, result)
    assert result.status == view.status == expected_status
    assert result.attempts == len(calls) == request_count
    assert view.validated == (expected_status == "valid")
    if result.status == "valid":
        assert result.validation == validate_plan(context, result.plan)
        assert result.validation.valid
        for activity in context.activities:
            if activity.fixed:
                scheduled = next(item for item in result.plan.scheduled if item.activity_id == activity.id)
                assert (scheduled.start_minute, scheduled.duration_minutes) == (activity.start_minute, activity.duration_minutes)
        assert len(view.schedule) == len(result.plan.scheduled)
        if scenario is late_start:
            assert result.validation.postponed_ids == ["reading"]
        else:
            assert result.validation.moved_or_adjusted_ids == ["study"]
            assert result.validation.kept_ids == ["call"]
    else:
        assert result.plan is None
        assert [issue.code for issue in result.issues] == ["FIXED_BUSY_CONFLICT"]
    app = render_pipeline_result(context, result)
    assert bool(app.success) == view.validated
    app.run()
    assert not app.exception
    assert len(calls) == request_count  # Presentation/rerender never invokes the provider.


def test_transport_correction_to_validated_presentation(mock_provider):
    context, corrected = converted_scenario(unexpected_event)
    invalid = corrected.model_copy(deep=True)
    invalid.scheduled[0].start_minute = 780  # Study now overlaps the visitor.
    provider, calls = mock_provider(invalid, corrected)
    result = run_agent(context, provider)
    assert result.status == "valid"
    assert result.attempts == len(calls) == 2
    feedback = json.loads(json.loads(calls[1].content)["messages"][1]["content"])
    assert feedback["previous_proposal"] == invalid.model_dump(mode="json")
    assert feedback["validation_issues"] == [issue.model_dump(mode="json") for issue in validate_plan(context, invalid).issues]
    assert [event.outcome for event in result.trace] == ["clear", "invalid", "valid"]
    assert prepare_agent_result(context, result).validated
    assert render_pipeline_result(context, result).success
    assert len(calls) == 2


def test_two_invalid_proposals_are_not_reported_as_impossible(mock_provider):
    context, _ = converted_scenario(late_start)
    provider, calls = mock_provider(ProposedPlan(), ProposedPlan())
    result = run_agent(context, provider)
    view = prepare_agent_result(context, result)
    assert result.status == "invalid"
    assert result.attempts == len(calls) == 2
    assert result.plan is None
    assert result.issues == tuple(validate_plan(context, ProposedPlan()).issues)
    assert not view.validated
    assert "does not prove the day is impossible" in view.message
    app = render_pipeline_result(context, result)
    assert app.error and not app.success
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["timeout", 403, 429, 500, "malformed-json"])
def test_transport_failures_are_terminal_and_sanitized(failure, mock_provider):
    context, _ = converted_scenario(late_start)
    sensitive = "private-raw-body-" + TEST_KEY

    def timeout(request):
        raise httpx.ReadTimeout(sensitive, request=request)

    if failure == "timeout":
        response = timeout
    elif failure == "malformed-json":
        response = sensitive  # Invalid JSON in an otherwise normal SDK completion.
    else:
        response = httpx.Response(failure, json={"error": {"message": sensitive}})
    provider, calls = mock_provider(response)
    result = run_agent(context, provider)
    # Adapter parse failures raise MetaProviderError; agent maps all adapter exceptions
    # to its existing safe provider_error terminal status, without an internal correction.
    assert result.status == "provider_error"
    assert result.attempts == len(calls) == 1
    assert result.plan is None
    assert result.trace[-1].error_codes == ("PROVIDER_ERROR",)
    view = prepare_agent_result(context, result)
    assert not view.validated
    assert sensitive not in repr(result.trace) + repr(view)
    assert TEST_KEY not in repr(result.trace) + repr(view)
    assert all(activity.title not in repr(result.trace) for activity in context.activities)
    app = render_pipeline_result(context, result)
    assert app.error and not app.success
    assert len(calls) == 1  # HTTP 429/500 must not trigger SDK retries.


def test_completed_transport_result_is_discarded_for_changed_input(mock_provider):
    context, proposal = converted_scenario(late_start)
    provider, calls = mock_provider(proposal)
    result = run_agent(context, provider)
    app = render_pipeline_result(context, result)
    assert app.success
    changed = context.model_copy(deep=True)
    changed.busy_windows.append(BusyWindow(start_minute=600, end_minute=660, label="New interruption"))
    app.session_state["context"] = changed
    app.run()
    assert not app.success
    assert RESULT_KEY not in app.session_state
    assert not prepare_agent_result(changed, result).validated
    app.session_state["context"] = context
    app.run()
    assert not app.success
    assert not app.exception
    assert len(calls) == 1


def test_ordinary_streamlit_rerenders_never_invoke_meta(monkeypatch):
    def forbidden_provider(*args, **kwargs):
        pytest.fail("Production UI must not invoke MetaProvider in M4A")
    monkeypatch.setattr(MetaProvider, "__call__", forbidden_provider)
    app = AppTest.from_file(str(APP)).run()
    app.run()
    app.selectbox[0].select_index(1).run()
    app.radio[0].set_value("Custom day").run()
    app.number_input[0].set_value(4).run()
    assert app.button[0].disabled
    assert RESULT_KEY not in app.session_state
    assert not app.exception
