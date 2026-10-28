"""AgentResult fixtures for presentation tests only; no simulated application provider."""

from dataclasses import replace
from datetime import time
from pathlib import Path
import socket

import httpx
import pytest
import requests
from streamlit.testing.v1 import AppTest

from core.agent import AgentResult, TraceEvent
import core.agent
from core.models import Activity, BusyWindow, DayContext, ProposedPlan, ScheduledItem, ValidationIssue
from core.presentation import input_fingerprint, prepare_agent_result
from core.validator import detect_hard_conflicts, validate_plan
from ui.agent_result import INPUT_KEY, RESULT_KEY, SavedAgentResult, current_agent_result, store_agent_result

APP = Path(__file__).resolve().parents[1] / "app.py"
HARNESS = """
import streamlit as st
from ui.agent_result import render_agent_result
render_agent_result(st.session_state['context'], st.session_state['result'])
"""


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Presentation must not invoke HTTP or connect a socket")
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        # Windows asyncio creates a localhost socketpair for its internal wakeup pipe.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        blocked()

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(core.agent, "run_agent", blocked)


@pytest.fixture
def context():
    # Matches the production custom-day defaults, so session binding is tested end-to-end.
    return DayContext(day_start_minute=420, day_end_minute=1320, now_minute=480,
                      activities=[Activity(id=f"activity_{i}", title=f"Activity {i}",
                                           start_minute=(8 + i) * 60, duration_minutes=60)
                                  for i in range(1, 4)])


@pytest.fixture
def valid_result(context):
    proposal = ProposedPlan(scheduled=[
        ScheduledItem(activity_id="activity_1", start_minute=540, duration_minutes=60),
        ScheduledItem(activity_id="activity_2", start_minute=840, duration_minutes=60),
    ], postponed_ids=["activity_3"])
    return AgentResult("valid", (TraceEvent("preflight", 0, "clear"),
                                  TraceEvent("proposal", 1, "valid")),
                       proposal, validate_plan(context, proposal))


def terminal_fixture(status, context, valid_result):
    if status == "valid":
        return context, valid_result
    if status == "infeasible":
        context = context.model_copy(deep=True)
        context.activities[0].fixed = True
        context.busy_windows.append(BusyWindow(start_minute=540, end_minute=600, label="Visitor"))
        issues = tuple(detect_hard_conflicts(context))
        return context, AgentResult(status, (TraceEvent("preflight", 0, "infeasible",
                                                       ("FIXED_BUSY_CONFLICT",)),), hard_conflicts=issues)
    if status == "invalid":
        validation = validate_plan(context, ProposedPlan())
        trace = (TraceEvent("preflight", 0, "clear"),
                 TraceEvent("proposal", 1, "invalid", ("MISSING_ACTIVITY",)),
                 TraceEvent("proposal", 2, "invalid", ("MISSING_ACTIVITY",)))
        return context, AgentResult(status, trace, validation=validation)
    code = "PROVIDER_ERROR" if status == "provider_error" else "MALFORMED_PROPOSAL"
    # Even an inconsistent stale success must never be shown for a failed terminal status.
    return context, AgentResult(status, (TraceEvent("preflight", 0, "clear"),
                                        TraceEvent("proposal", 1, "error", (code,))),
                                 plan=valid_result.plan, validation=valid_result.validation)


@pytest.mark.parametrize("status", ["valid", "infeasible", "invalid", "provider_error", "malformed_proposal"])
def test_terminal_status_presentation(context, valid_result, status):
    context, result = terminal_fixture(status, context, valid_result)
    view = prepare_agent_result(context, result)
    assert view.status == status
    assert view.validated == (status == "valid")
    assert len(view.trace) <= 3
    if status != "valid":
        assert not view.schedule
        assert not view.dispositions
    if status == "invalid":
        assert "two attempts" in view.message
        assert "does not prove" in view.message
        assert view.issues == ("MISSING_ACTIVITY",)
    if status == "infeasible":
        assert "FIXED_BUSY_CONFLICT" in view.issues[0]
        assert "Visitor" in view.issues[0]


@pytest.mark.parametrize("status", ["valid", "infeasible", "invalid", "provider_error", "malformed_proposal"])
def test_terminal_status_apptest(context, valid_result, status):
    context, result = terminal_fixture(status, context, valid_result)
    app = AppTest.from_string(HARNESS)
    app.session_state["context"] = context
    app.session_state["result"] = result
    app.run()
    assert not app.exception
    assert any(f"status: {status}" in item.value for item in app.caption)
    assert bool(app.success) == (status == "valid")
    assert bool(app.error) == (status != "valid")
    assert len(app.dataframe[-1].value) <= 3
    app.run()  # Rerender also must not invoke any provider/network.
    assert not app.exception


def test_dispositions_come_from_python_not_stored_summary(context, valid_result):
    valid_result.validation.kept_ids = ["forged-id"]
    view = prepare_agent_result(context, valid_result)
    assert view.validated
    assert dict(view.dispositions) == {
        "Kept": ("Activity 1 (activity_1)",),
        "Moved / adjusted": ("Activity 2 (activity_2)",),
        "Postponed": ("Activity 3 (activity_3)",),
    }
    assert [row["Start"] for row in view.schedule] == ["09:00", "14:00"]


@pytest.mark.parametrize("tamper", ["missing_plan", "missing_validation", "failed_validation", "changed_plan", "malformed_plan", "changed_context"])
def test_no_false_valid(context, valid_result, tamper):
    if tamper == "missing_plan":
        valid_result = replace(valid_result, plan=None)
    elif tamper == "missing_validation":
        valid_result = replace(valid_result, validation=None)
    elif tamper == "failed_validation":
        valid_result.validation.valid = False
    elif tamper == "changed_plan":
        valid_result.plan.scheduled[0].start_minute = 0
    elif tamper == "malformed_plan":
        valid_result.plan.scheduled[0].duration_minutes = 0
    else:
        context.now_minute = 700
    view = prepare_agent_result(context, valid_result)
    assert not view.validated
    assert not view.schedule
    app = AppTest.from_string(HARNESS)
    app.session_state["context"] = context
    app.session_state["result"] = valid_result
    app.run()
    assert not app.success
    assert app.error
    assert not app.exception


def test_trace_and_failure_messages_are_bounded_and_safe(context, valid_result):
    secret = "private-raw-error-body"
    trace = tuple(TraceEvent("proposal", 2, "error", (secret,) * 30) for _ in range(100))
    valid_result.validation.issues.append(ValidationIssue(code=secret, message=secret))
    result = replace(valid_result, status="provider_error", trace=trace)
    view = prepare_agent_result(context, result)
    assert len(view.trace) == 3
    assert secret not in repr(view)
    assert len(view.trace[0]["Error codes"].split(", ")) == 10
    assert not view.validated


def test_input_fingerprint_covers_scope_and_all_context_fields(context):
    original = input_fingerprint(context, "custom")
    for update in ({"now_minute": 481}, {"day_start_minute": 421}, {"day_end_minute": 1321},
                   {"busy_windows": [BusyWindow(start_minute=900, end_minute=960)]}):
        assert input_fingerprint(context.model_copy(update=update), "custom") != original
    assert input_fingerprint(context, "example:A") != original
    copy = context.model_copy(deep=True)
    copy.activities[0].priority = "high"
    assert input_fingerprint(copy, "custom") != original


def test_session_clears_results_and_rejects_late_results(context, valid_result):
    state = {}
    assert current_agent_result(state, context, "custom") is None
    assert store_agent_result(state, context, "custom", valid_result)
    assert current_agent_result(state, context, "custom") == valid_result
    changed = context.model_copy(update={"now_minute": 481})
    assert current_agent_result(state, changed, "custom") is None
    assert RESULT_KEY not in state
    assert not store_agent_result(state, context, "custom", valid_result)
    assert current_agent_result(state, context, "custom") is None  # Switching back cannot restore it.
    assert store_agent_result(state, context, "custom", valid_result)
    assert current_agent_result(state, None, "custom") is None
    assert RESULT_KEY not in state


def test_stale_or_unbound_session_records_are_discarded(context, valid_result):
    state = {}
    current_agent_result(state, context, "custom")
    state[RESULT_KEY] = valid_result  # No input binding: never display it.
    assert current_agent_result(state, context, "custom") is None
    state[RESULT_KEY] = SavedAgentResult(input_fingerprint(context, "example:A"), valid_result)
    assert current_agent_result(state, context, "custom") is None
    assert RESULT_KEY not in state


@pytest.mark.parametrize("change", ["name", "start", "duration", "invalid_duration", "priority", "fixed", "shorten", "now", "day_start", "day_end", "count", "busy", "mode"])
def test_full_app_discards_old_results_on_input_change(context, valid_result, change):
    app = AppTest.from_file(str(APP)).run()
    app.radio[0].set_value("Custom day").run()
    assert app.session_state[INPUT_KEY] == input_fingerprint(context, "custom")
    app.session_state[RESULT_KEY] = SavedAgentResult(app.session_state[INPUT_KEY], valid_result)
    app.run()
    assert app.success
    if change == "name":
        app.text_input(key="activity_1_name").set_value("Renamed").run()
    elif change == "start":
        app.time_input(key="activity_1_start").set_value(time(9, 30)).run()
    elif change in ("duration", "invalid_duration"):
        app.number_input(key="activity_1_duration").set_value(30 if change == "duration" else 0).run()
    elif change == "priority":
        app.selectbox(key="activity_1_priority").set_value("high").run()
    elif change in ("fixed", "shorten"):
        app.checkbox(key=f"activity_1_{change}").check().run()
    elif change in ("now", "day_start", "day_end"):
        index = {"now": 0, "day_start": 1, "day_end": 2}[change]
        app.time_input[index].set_value(time(8, 30)).run()
    elif change == "count":
        app.number_input[0].set_value(4).run()
    elif change == "busy":
        app.number_input[-1].set_value(1).run()
    else:
        app.radio[0].set_value("Example scenarios").run()
    assert RESULT_KEY not in app.session_state
    if change != "mode":  # Example A still correctly shows its own hand-authored fixture success.
        assert not app.success
    assert not app.exception


def test_production_launch_and_rerender_do_not_generate_results():
    app = AppTest.from_file(str(APP)).run()
    assert app.button[0].disabled
    assert RESULT_KEY not in app.session_state
    app.run()
    app.radio[0].set_value("Custom day").run()
    assert not app.success
    assert not app.exception
    assert RESULT_KEY not in app.session_state
