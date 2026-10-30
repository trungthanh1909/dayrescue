"""Offline CLI tests; mocked completions here are never evidence of Muse output."""

import json
import socket
from unittest.mock import Mock

import httpx
import pytest
import requests

from core.meta_client import MetaProvider, MetaProviderError
from core.scenarios import unexpected_event
from scripts import live_structured_probe as probe

SECRET = "offline-probe-secret-canary"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Live network forbidden in probe tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(probe, "load_dotenv", Mock())
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL", raising=False)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    instance = Mock(return_value=unexpected_event()[1])
    monkeypatch.setattr(probe, "MetaProvider", Mock(return_value=instance))
    return instance


def output(capsys, *, error=False):
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert not (captured.out if error else captured.err)
    return json.loads(captured.err if error else captured.out)


def test_default_gate_does_not_load_credentials_or_construct_provider(monkeypatch, capsys):
    constructor = Mock(side_effect=AssertionError("Must not construct"))
    monkeypatch.setattr(probe, "MetaProvider", constructor)
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    assert probe.main([]) == 0
    assert "PROBE NOT RUN" in capsys.readouterr().out
    probe.load_dotenv.assert_not_called()
    constructor.assert_not_called()


@pytest.mark.parametrize("flag", ["--liv", "--li", "--live=true"])
def test_requires_exact_explicit_live_flag(flag):
    with pytest.raises(SystemExit) as exc:
        probe.main([flag])
    assert exc.value.code == 2
    probe.load_dotenv.assert_not_called()


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_credentials_stop_before_construction(key, monkeypatch, capsys):
    if key is not None:
        monkeypatch.setenv("MODEL_API_KEY", key)
    constructor = Mock()
    monkeypatch.setattr(probe, "MetaProvider", constructor)
    assert probe.main(["--live"]) == 2
    assert output(capsys, error=True)["error_codes"] == ["MISSING_CREDENTIALS"]
    constructor.assert_not_called()


def test_valid_single_request_and_local_loading(provider, capsys, monkeypatch):
    monkeypatch.setenv("META_MODEL", "must-not-override-probe-model")
    provider.return_value.explanation = SECRET
    assert probe.main(["--live"]) == 0
    report = output(capsys)
    assert report["schema_parse"] == "SUCCESS"
    assert report["python_validation"] == "VALID"
    assert report["validation_issue_codes"] == []
    assert report["kept_ids"] == ["call"]
    assert report["moved_or_adjusted_ids"] == ["study"]
    assert report["postponed_ids"] == []
    assert report["fixed_call_preserved"] is True
    assert report["unexpected_event_respected"] is True
    assert "optimality" in report["quality"]
    probe.load_dotenv.assert_called_once_with(probe.ROOT / ".env", override=False, interpolate=False)
    probe.MetaProvider.assert_called_once_with(model="muse-spark-1.3", reasoning_effort="low")
    provider.assert_called_once()
    request = provider.call_args.args[0]
    assert request.context == unexpected_event()[0]
    assert request.attempt == 1
    assert request.previous_proposal is None
    assert request.validation_issues == ()
    provider.close.assert_called_once_with()


@pytest.mark.parametrize("change,code,fixed,event", [
    ("busy", "BUSY_OVERLAP", True, False),
    ("call", "FIXED_MOVED", False, True),
])
def test_invalid_proposal_has_no_correction(provider, capsys, change, code, fixed, event):
    proposal = provider.return_value
    if change == "busy":
        proposal.scheduled[0].start_minute = 13 * 60
    else:
        proposal.scheduled[1].start_minute = 12 * 60
    assert probe.main(["--live"]) == 1
    report = output(capsys)
    assert report["schema_parse"] == "SUCCESS"
    assert report["python_validation"] == "INVALID"
    assert code in report["validation_issue_codes"]
    assert report["fixed_call_preserved"] is fixed
    assert report["unexpected_event_respected"] is event
    provider.assert_called_once()
    provider.close.assert_called_once()


def test_postponing_useful_work_is_valid_but_potentially_low_quality(provider, capsys):
    provider.return_value.scheduled.pop(0)
    provider.return_value.postponed_ids = ["study"]
    assert probe.main(["--live"]) == 0
    report = output(capsys)
    assert report["python_validation"] == "VALID"
    assert report["postponed_ids"] == ["study"]
    assert report["quality"].startswith("VALID_BUT_POTENTIALLY_LOW_QUALITY")


@pytest.mark.parametrize("malformed", ["dict", "mutated"])
def test_schema_failure_is_safe_and_closes(provider, capsys, malformed):
    if malformed == "dict":
        provider.return_value = {"valid": True, "explanation": SECRET}
    else:
        provider.return_value.scheduled[0].duration_minutes = -1
    assert probe.main(["--live"]) == 1
    report = output(capsys, error=True)
    assert report == {"schema_parse": "FAILURE", "python_validation": "NOT_RUN",
                      "error_codes": ["MALFORMED_PROPOSAL"]}
    provider.assert_called_once()
    provider.close.assert_called_once()


@pytest.mark.parametrize("failure,expected", [
    (MetaProviderError("TIMEOUT"), "TIMEOUT"),
    (MetaProviderError("SDK_ERROR"), "SDK_ERROR"),
    (MetaProviderError(SECRET), "PROBE_ERROR"),
    (RuntimeError("Authorization: Bearer " + SECRET), "PROBE_ERROR"),
])
def test_failures_are_codes_only_without_retry(provider, capsys, failure, expected):
    provider.side_effect = failure
    assert probe.main(["--live"]) == 1
    report = output(capsys, error=True)
    assert report["error_codes"] == [expected]
    assert report["python_validation"] == "NOT_RUN"
    provider.assert_called_once()
    provider.close.assert_called_once()


def test_constructor_failure_is_sanitized(provider, capsys):
    probe.MetaProvider.side_effect = RuntimeError(SECRET)
    assert probe.main(["--live"]) == 1
    assert output(capsys, error=True)["error_codes"] == ["PROBE_ERROR"]
    provider.assert_not_called()


def test_close_failure_is_sanitized_without_retry(provider, capsys):
    provider.close.side_effect = RuntimeError(SECRET)
    assert probe.main(["--live"]) == 1
    assert output(capsys, error=True)["error_codes"] == ["PROBE_ERROR"]
    provider.assert_called_once()
    provider.close.assert_called_once()


@pytest.mark.parametrize("response,expected", [
    ("valid", None), ("malformed", "MALFORMED_PROPOSAL"),
    ("length", "TRUNCATED_RESPONSE"), (429, "SDK_ERROR"),
    (500, "SDK_ERROR"), ("timeout", "TIMEOUT"),
])
def test_script_with_real_sdk_mock_transport(monkeypatch, capsys, response, expected):
    monkeypatch.setenv("MODEL_API_KEY", SECRET)
    calls = []
    instances = []

    def handler(request):
        calls.append(request)
        assert len(calls) == 1
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "low"
        assert body["model"] == "muse-spark-1.3"
        assert body["max_completion_tokens"] == 2048
        assert body["response_format"]["type"] == "json_schema"
        assert "temperature" not in body
        assert json.loads(body["messages"][1]["content"])["attempt"] == 1
        assert request.extensions["timeout"] == {
            "connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0,
        }
        if response == "timeout":
            raise httpx.ReadTimeout(SECRET, request=request)
        if isinstance(response, int):
            return httpx.Response(response, json={"error": {"message": SECRET}})
        content = unexpected_event()[1].model_dump_json() if response != "malformed" else SECRET
        return httpx.Response(200, json={
            "id": "offline-probe", "object": "chat.completion", "created": 0,
            "model": "muse-spark-1.3", "choices": [{"index": 0,
                "finish_reason": "length" if response == "length" else "stop",
                "message": {"role": "assistant", "content": content}}],
        })

    def construct(**kwargs):
        instance = MetaProvider(http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
        assert instance._client.max_retries == 0
        instances.append(instance)
        return instance

    monkeypatch.setattr(probe, "MetaProvider", construct)
    assert probe.main(["--live"]) == (1 if expected else 0)
    report = output(capsys, error=expected is not None)
    if expected:
        assert report["error_codes"] == [expected]
    else:
        assert report["python_validation"] == "VALID"
    assert len(calls) == 1
    assert len(instances) == 1
    assert instances[0]._client.is_closed()
