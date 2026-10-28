"""Real SDK + in-memory HTTP transport only; responses are test fixtures, not Muse output."""

import json
import socket
import traceback

import httpx
import pytest

from core.agent import ProposalRequest, run_agent
from core.meta_client import MetaProvider, MetaProviderError
from core.models import Activity, DayContext, ProposedPlan, ScheduledItem
from core.validator import validate_plan

TEST_KEY = "offline-test-credential"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Real network access is forbidden in offline provider tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL", raising=False)


@pytest.fixture
def context():
    return DayContext(now_minute=480, activities=[
        Activity(id="study", title="Study", start_minute=600, duration_minutes=60),
    ])


def plan(start=600):
    return ProposedPlan(scheduled=[ScheduledItem(activity_id="study", start_minute=start,
                                                duration_minutes=60)])


def completion(content=None, finish="stop"):
    return {"id": "test-completion", "object": "chat.completion", "created": 0,
            "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def provider_factory():
    providers = []

    def make(handler, **kwargs):
        transport = httpx.MockTransport(handler)
        provider = MetaProvider(api_key=TEST_KEY,
                                http_client=httpx.Client(transport=transport), **kwargs)
        providers.append(provider)
        return provider
    yield make
    for provider in providers:
        provider.close()


def test_first_request_payload_and_bounds(context, provider_factory):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=completion(plan().model_dump_json()))

    provider = provider_factory(handler)
    assert not seen  # Construction must not call the API.
    result = provider(ProposalRequest(context, 1))
    assert result == plan()
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {TEST_KEY}"
    assert request.extensions["timeout"] == {"connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0}
    body = json.loads(request.content)
    assert body["model"] == "muse-spark-1.3"
    assert body["max_completion_tokens"] == 2048
    assert body["stream"] is False
    instructions, user = body["messages"]
    assert instructions["role"] == "developer"
    for constraint in ("exactly once", "Fixed", "min_duration_minutes", "now_minute", "half-open", "not overlap"):
        assert constraint in instructions["content"]
    assert user["role"] == "user"
    assert json.loads(user["content"]) == {"attempt": 1, "context": context.model_dump(mode="json")}
    assert TEST_KEY not in user["content"]
    output = body["response_format"]
    assert output["type"] == "json_schema"
    assert output["json_schema"]["schema"] == ProposedPlan.model_json_schema()
    assert "valid" not in output["json_schema"]["schema"]["properties"]


def test_correction_through_agent_transmits_real_feedback(context, provider_factory):
    requests = []
    bad = plan(420)

    def handler(request):
        requests.append(json.loads(request.content))
        proposal = bad if len(requests) == 1 else plan()
        return httpx.Response(200, json=completion(proposal.model_dump_json()))

    result = run_agent(context, provider_factory(handler))
    assert result.status == "valid"
    assert result.attempts == len(requests) == 2
    correction = json.loads(requests[1]["messages"][1]["content"])
    assert correction["attempt"] == 2
    assert correction["context"] == context.model_dump(mode="json")
    assert correction["previous_proposal"] == bad.model_dump(mode="json")
    assert correction["validation_issues"] == [i.model_dump(mode="json") for i in validate_plan(context, bad).issues]


def test_configured_model(context, provider_factory, monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content)["model"])
        return httpx.Response(200, json=completion(plan().model_dump_json()))

    monkeypatch.setenv("META_MODEL", "test-env-model")
    provider_factory(handler)(ProposalRequest(context, 1))
    provider_factory(handler, model="explicit-model")(ProposalRequest(context, 1))
    assert seen == ["test-env-model", "explicit-model"]


@pytest.mark.parametrize("key", [None, "", "  "])
def test_missing_credentials_never_constructs_network_request(key):
    with pytest.raises(MetaProviderError, match="MISSING_CREDENTIALS"):
        MetaProvider(api_key=key)


def test_environment_credentials(context, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", TEST_KEY)
    seen = []

    def handler(request):
        seen.append(request.headers["authorization"])
        return httpx.Response(200, json=completion(plan().model_dump_json()))

    provider = MetaProvider(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        provider(ProposalRequest(context, 1))
    finally:
        provider.close()
    assert seen == [f"Bearer {TEST_KEY}"]


@pytest.mark.parametrize("content,finish,code", [
    (None, "stop", "EMPTY_RESPONSE"),
    ("  ", "stop", "EMPTY_RESPONSE"),
    ("not JSON", "stop", "MALFORMED_PROPOSAL"),
    ('{"scheduled": [', "stop", "MALFORMED_PROPOSAL"),
    ('{"valid": true}', "stop", "MALFORMED_PROPOSAL"),
    ('{"scheduled": [{"duration_minutes": 0}]}', "stop", "MALFORMED_PROPOSAL"),
    ("[]", "stop", "MALFORMED_PROPOSAL"),
    ("{}", "length", "TRUNCATED_RESPONSE"),
    (None, "length", "TRUNCATED_RESPONSE"),
    ("{}", "content_filter", "UNSUPPORTED_RESPONSE"),
    (None, "tool_calls", "UNSUPPORTED_RESPONSE"),
    ("x" * 32769, "stop", "MALFORMED_RESPONSE"),
])
def test_invalid_outputs(context, provider_factory, content, finish, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=completion(content, finish))

    with pytest.raises(MetaProviderError) as exc:
        provider_factory(handler)(ProposalRequest(context, 1))
    assert exc.value.code == code
    assert len(calls) == 1


@pytest.mark.parametrize("envelope,code", [
    ({"choices": []}, "EMPTY_RESPONSE"),
    ({}, "MALFORMED_RESPONSE"),
    ({"choices": [{}]}, "UNSUPPORTED_RESPONSE"),
    ({"choices": [{"finish_reason": "stop"}]}, "MALFORMED_RESPONSE"),
])
def test_bad_envelopes(context, provider_factory, envelope, code):
    with pytest.raises(MetaProviderError) as exc:
        provider_factory(lambda r: httpx.Response(200, json=envelope))(ProposalRequest(context, 1))
    assert exc.value.code == code


@pytest.mark.parametrize("change", ["refusal", "tool_calls", "extra_choice", "bad_content"])
def test_unsupported_or_ambiguous_responses(context, provider_factory, change):
    envelope = completion(plan().model_dump_json())
    message = envelope["choices"][0]["message"]
    if change == "refusal":
        message["refusal"] = "Refused"
    elif change == "tool_calls":
        message["tool_calls"] = [{"id": "test-tool", "type": "function",
                                  "function": {"name": "do_not_execute", "arguments": "{}"}}]
    elif change == "extra_choice":
        envelope["choices"].append(envelope["choices"][0].copy())
    else:
        message["content"] = {"unexpected": "shape"}
    expected = "UNSUPPORTED_RESPONSE" if change in ("refusal", "tool_calls") else "MALFORMED_RESPONSE"
    with pytest.raises(MetaProviderError) as exc:
        provider_factory(lambda r: httpx.Response(200, json=envelope))(ProposalRequest(context, 1))
    assert exc.value.code == expected


def test_non_json_http_response_is_sanitized(context, provider_factory):
    provider = provider_factory(lambda r: httpx.Response(200, text="private response body"))
    with pytest.raises(MetaProviderError) as exc:
        provider(ProposalRequest(context, 1))
    assert "private response body" not in str(exc.value)
    assert exc.value.code in ("SDK_ERROR", "MALFORMED_RESPONSE")


@pytest.mark.parametrize("failure", [400, 401, 403, 408, 429, 500, "connect", "timeout"])
def test_sdk_errors_are_sanitized_without_retries(context, provider_factory, failure, capsys):
    calls = []
    sensitive = "raw-sensitive-error-body-" + TEST_KEY

    def handler(request):
        calls.append(request)
        if failure == "connect":
            raise httpx.ConnectError(sensitive, request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout(sensitive, request=request)
        return httpx.Response(failure, json={"error": {"message": sensitive}})

    provider = provider_factory(handler)
    with pytest.raises(MetaProviderError) as exc:
        provider(ProposalRequest(context, 1))
    expected = "TIMEOUT" if failure == "timeout" else "SDK_ERROR"
    assert exc.value.code == expected
    assert len(calls) == 1  # Actual transport count verifies zero SDK retries.
    public_traceback = "".join(traceback.format_exception(exc.value))
    assert sensitive not in public_traceback
    assert TEST_KEY not in repr(exc.value)
    assert capsys.readouterr() == ("", "")
    result = run_agent(context, provider)
    assert result.status == "provider_error"
    assert result.attempts == 1
    assert result.trace[-1].error_codes == ("PROVIDER_ERROR",)
    assert sensitive not in repr(result.trace)
    assert len(calls) == 2  # Two separate runs, one HTTP attempt each.


def test_adapter_does_not_claim_semantic_validity(context, provider_factory):
    bad = plan(420)
    provider = provider_factory(lambda r: httpx.Response(200, json=completion(bad.model_dump_json())))
    proposal = provider(ProposalRequest(context, 1))
    assert proposal == bad
    assert not validate_plan(context, proposal).valid


@pytest.mark.parametrize("attempt,has_previous", [(0, False), (3, True), (2, False), (1, True)])
def test_invalid_request_does_not_call_transport(context, provider_factory, attempt, has_previous):
    def handler(request):
        pytest.fail("Invalid request must not reach transport")
    request = ProposalRequest(context, attempt, previous_proposal=plan() if has_previous else None)
    with pytest.raises(MetaProviderError, match="INVALID_REQUEST"):
        provider_factory(handler)(request)


def test_request_content_size_is_bounded(context, provider_factory):
    def handler(request):
        pytest.fail("Oversized request must not reach transport")
    previous = ProposedPlan(postponed_ids=["x" * 32769])
    issues = tuple(validate_plan(context, plan(420)).issues)
    request = ProposalRequest(context, 2, previous, issues)
    with pytest.raises(MetaProviderError, match="REQUEST_TOO_LARGE"):
        provider_factory(handler)(request)


def test_empty_model_configuration_is_explicit():
    with pytest.raises(MetaProviderError, match="INVALID_CONFIGURATION"):
        MetaProvider(api_key=TEST_KEY, model=" ")


def test_invalid_client_configuration_is_sanitized():
    with pytest.raises(MetaProviderError, match="INVALID_CONFIGURATION") as exc:
        MetaProvider(api_key=TEST_KEY, http_client=object())
    assert TEST_KEY not in str(exc.value)
