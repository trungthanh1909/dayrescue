"""Offline production click → agent → SDK/MockTransport → presentation checks."""

from datetime import time
import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from core.agent import AgentResult
import core.live_generation as live
from core.meta_client import MetaProvider
from core.models import Activity, DayContext, ProposedPlan, ScheduledItem
from core.presentation import input_fingerprint
from ui.agent_result import INPUT_KEY, RESULT_KEY, current_agent_result

APP = Path(__file__).resolve().parents[1] / "app.py"
SECRET = "offline-streamlit-credential-canary"
RAW_ERROR = "private-http-body-" + SECRET


def default_context():
    return DayContext(day_start_minute=420, day_end_minute=1320, now_minute=480,
                      activities=[Activity(id=f"activity_{i}", title=f"Activity {i}",
                                           start_minute=(8 + i) * 60, duration_minutes=60)
                                  for i in range(1, 4)])


def valid_plan():
    return ProposedPlan(scheduled=[
        ScheduledItem(activity_id="activity_1", start_minute=540, duration_minutes=60),
        ScheduledItem(activity_id="activity_2", start_minute=840, duration_minutes=60),
    ], postponed_ids=["activity_3"], explanation="**Untrusted rationale** <script>do_not_run()</script>")


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(live, "load_dotenv", Mock())


@pytest.fixture
def transport_provider(monkeypatch):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    instances = []

    def install(*responses):
        calls = []

        def handler(request):
            calls.append(request)
            assert len(calls) <= len(responses) <= 2
            body = json.loads(request.content)
            assert body["model"] == "muse-spark-1.3"
            assert body["reasoning_effort"] == "low"
            assert body["max_completion_tokens"] == 2048
            assert body["response_format"]["type"] == "json_schema"
            assert body["response_format"]["json_schema"]["strict"] is False
            assert "temperature" not in body
            assert request.extensions["timeout"] == {
                "connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0,
            }
            response = responses[len(calls) - 1]
            if callable(response):
                return response(request)
            if isinstance(response, httpx.Response):
                return response
            content = response.model_dump_json() if isinstance(response, ProposedPlan) else response
            return httpx.Response(200, json={
                "id": "offline-click", "object": "chat.completion", "created": 0,
                "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content}}],
            })

        def construct(**kwargs):
            instance = MetaProvider(http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
            assert instance._client.max_retries == 0
            instances.append(instance)
            return instance

        monkeypatch.setattr(live, "MetaProvider", construct)
        return calls

    yield install, instances
    for instance in instances:
        assert instance._client.is_closed()


def custom_app():
    app = AppTest.from_file(str(APP)).run()
    app.radio[0].set_value("Custom day").run()
    assert not app.exception
    return app


def click(app):
    app.button(key="generate_live_ai").click().run()
    assert not app.exception


def assert_safe(app, capsys, caplog):
    captured = capsys.readouterr()
    rendered = repr(app.get("root")) + str(app) + caplog.text + captured.out + captured.err
    assert SECRET not in rendered
    assert RAW_ERROR not in rendered
    assert not app.exception


@pytest.mark.parametrize("flag", [None, "0", "true", " 1", "1 "])
def test_gate_requires_exact_one(flag, monkeypatch):
    if flag is not None:
        monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", flag)
    provider = Mock()
    monkeypatch.setattr(live, "MetaProvider", provider)
    assert not live.live_ai_enabled()
    assert live.generate_live_result(default_context()).status == "provider_error"
    live.load_dotenv.assert_not_called()
    provider.assert_not_called()
    app = custom_app()
    assert app.button(key="generate_live_ai").disabled
    app.run()
    assert RESULT_KEY not in app.session_state


def test_opt_in_alone_never_invokes_on_startup_or_rerenders(transport_provider):
    install, instances = transport_provider
    calls = install(valid_plan())
    app = AppTest.from_file(str(APP)).run()
    assert app.button[0].disabled  # Examples never generate, even when enabled.
    app.run()
    app.selectbox[0].select_index(1).run()
    app.radio[0].set_value("Custom day").run()
    app.run()
    app.number_input[0].set_value(4).run()
    assert not app.button(key="generate_live_ai").disabled
    assert not calls and not instances
    live.load_dotenv.assert_not_called()


def test_one_click_valid_first_proposal_and_plain_rationale(transport_provider, capsys, caplog):
    install, instances = transport_provider
    calls = install(valid_plan())
    app = custom_app()
    assert not calls
    click(app)
    assert len(calls) == len(instances) == 1
    assert app.success
    assert "Python revalidated" in app.success[0].value
    assert any("status: valid" in item.value for item in app.caption)
    assert app.dataframe[-1].value["Attempt"].tolist() == [0, 1]
    assert any("Moved / adjusted" in item.value for item in app.markdown)
    assert any("Postponed" in item.value for item in app.markdown)
    assert app.text[0].value == valid_plan().explanation  # st.text, never Markdown/HTML.
    assert any("not independently verified" in item.value for item in app.subheader)
    app.run()
    assert len(calls) == 1
    live.load_dotenv.assert_called_once_with(live.ROOT / ".env", override=False, interpolate=False)
    assert_safe(app, capsys, caplog)


def test_correction_uses_exact_feedback_and_stops_at_two(transport_provider):
    install, _ = transport_provider
    calls = install(ProposedPlan(), valid_plan())
    app = custom_app()
    click(app)
    assert app.success
    assert len(calls) == 2
    request = json.loads(json.loads(calls[1].content)["messages"][1]["content"])
    assert request["attempt"] == 2
    assert request["previous_proposal"] == ProposedPlan().model_dump(mode="json")
    assert [issue["code"] for issue in request["validation_issues"]] == ["MISSING_ACTIVITY"] * 3
    assert app.dataframe[-1].value["Attempt"].tolist() == [0, 1, 2]
    app.run()
    assert len(calls) == 2


def test_both_invalid_never_show_valid_or_rationale(transport_provider):
    install, _ = transport_provider
    calls = install(ProposedPlan(), ProposedPlan())
    app = custom_app()
    click(app)
    assert len(calls) == 2
    assert not app.success and not app.text
    assert any("status: invalid" in item.value for item in app.caption)
    assert "does not prove" in app.error[-1].value
    assert len(app.dataframe[-1].value) == 3


def test_fixed_conflicts_skip_credentials_and_provider(transport_provider):
    install, instances = transport_provider
    calls = install(valid_plan())
    app = custom_app()
    app.checkbox(key="activity_1_fixed").check().run()
    app.checkbox(key="activity_2_fixed").check().run()
    app.time_input(key="activity_2_start").set_value(time(9)).run()
    click(app)
    assert not calls and not instances
    live.load_dotenv.assert_not_called()
    assert any("status: infeasible" in item.value for item in app.caption)
    assert not app.success


@pytest.mark.parametrize("failure", [403, 429, 500, "timeout", "malformed"])
def test_transport_failures_are_safe_terminal_errors(transport_provider, failure, capsys, caplog):
    install, _ = transport_provider

    def timeout(request):
        raise httpx.ReadTimeout(RAW_ERROR, request=request)

    response = (timeout if failure == "timeout" else RAW_ERROR if failure == "malformed" else
                httpx.Response(failure, json={"error": {"message": RAW_ERROR}}))
    calls = install(response)
    app = custom_app()
    click(app)
    assert len(calls) == 1
    assert not app.success and not app.text
    assert any("status: provider_error" in item.value for item in app.caption)
    assert app.error
    app.run()
    assert len(calls) == 1
    assert_safe(app, capsys, caplog)


@pytest.mark.parametrize("failure_stage", ["constructor", "close", "malformed_data"])
def test_other_failures_safe_and_client_closed(monkeypatch, failure_stage, capsys, caplog):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    provider = Mock(return_value={"valid": True, "explanation": RAW_ERROR})
    constructor = Mock(return_value=provider)
    monkeypatch.setattr(live, "MetaProvider", constructor)
    if failure_stage == "constructor":
        constructor.side_effect = RuntimeError(RAW_ERROR)
    elif failure_stage == "close":
        provider.return_value = valid_plan()
        provider.close.side_effect = RuntimeError(RAW_ERROR)
    app = custom_app()
    click(app)
    assert not app.success and not app.text
    status = "malformed_proposal" if failure_stage == "malformed_data" else "provider_error"
    assert any(f"status: {status}" in item.value for item in app.caption)
    if failure_stage != "constructor":
        provider.close.assert_called_once()
        provider.assert_called_once()
    assert_safe(app, capsys, caplog)


def test_missing_credentials_are_safe(monkeypatch, capsys, caplog):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    app = custom_app()
    click(app)
    assert any("status: provider_error" in item.value for item in app.caption)
    assert not app.success
    assert_safe(app, capsys, caplog)


@pytest.mark.parametrize("change", ["input", "invalid_input", "mode"])
def test_real_click_result_invalidated_and_never_restored(transport_provider, change):
    install, _ = transport_provider
    calls = install(valid_plan())
    app = custom_app()
    click(app)
    assert app.success
    if change == "input":
        app.text_input(key="activity_1_name").set_value("Changed").run()
        app.text_input(key="activity_1_name").set_value("Activity 1").run()
    elif change == "invalid_input":
        app.number_input(key="activity_1_duration").set_value(0).run()
        app.number_input(key="activity_1_duration").set_value(60).run()
    else:
        app.radio[0].set_value("Example scenarios").run()
        app.radio[0].set_value("Custom day").run()
    assert RESULT_KEY not in app.session_state
    assert not app.success and not app.text
    assert len(calls) == 1


def test_active_binding_changes_during_invocation_rejects_result(monkeypatch):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    # Use a Streamlit harness to emulate a newer input becoming active in flight.
    import ui.live_generation as ui_live
    original = ui_live.generate_live_result

    def changed_during_call(context):
        import streamlit as st
        changed = context.model_copy(update={"now_minute": 481})
        current_agent_result(st.session_state, changed, "custom")
        return AgentResult("valid", ())

    monkeypatch.setattr(ui_live, "generate_live_result", changed_during_call)
    app = custom_app()
    click(app)
    assert not app.success
    assert RESULT_KEY not in app.session_state
    assert app.session_state[INPUT_KEY] != input_fingerprint(default_context(), "custom")
    assert any("Inputs changed" in item.value for item in app.info)
    monkeypatch.setattr(ui_live, "generate_live_result", original)


def test_repeated_click_error_replaces_previous_success(transport_provider):
    install, _ = transport_provider
    first_calls = install(valid_plan())
    app = custom_app()
    click(app)
    assert app.success
    second_calls = install(httpx.Response(500, json={"error": {"message": RAW_ERROR}}))
    click(app)
    assert not app.success and not app.text
    assert len(first_calls) == len(second_calls) == 1


def test_tampered_valid_result_cannot_display_valid_or_rationale(transport_provider):
    install, _ = transport_provider
    install(valid_plan())
    app = custom_app()
    click(app)
    app.session_state[RESULT_KEY].result.plan.scheduled[0].start_minute = 0
    app.run()
    assert not app.success and not app.text
    assert app.error


def test_rationale_is_length_limited(transport_provider):
    install, _ = transport_provider
    proposal = valid_plan()
    proposal.explanation = "r" * 2000
    install(proposal)
    app = custom_app()
    click(app)
    assert app.text[0].value == "r" * 1000
