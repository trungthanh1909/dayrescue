"""Local HTTP contracts through ASGI; Muse transport is in-memory only."""
import asyncio
from copy import deepcopy
from datetime import time
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from api.app import ORIGINS, create_app
from core import live_generation as live
from core.meta_client import MetaProvider
from core.models import ProposedPlan
from core.scenarios import unexpected_event

HEADERS = {"Origin": ORIGINS[0], "X-DayRescue-Action": "rescue"}
CANARY = "private-test-provider-canary"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(live, "load_dotenv", Mock())
    return create_app()


def day_body():
    context, _ = unexpected_event()
    return {"date": "2026-11-04", "revision": 0, "now": "11:00", "day_start": "07:00", "day_end": "22:00",
            "activities": [{"id": a.id, "title": a.title, "start_time": f"{a.start_minute//60:02d}:{a.start_minute%60:02d}",
                "duration_minutes": a.duration_minutes, "priority": a.priority, "fixed": a.fixed,
                "min_duration_minutes": a.min_duration_minutes} for a in context.activities],
            "busy_windows": [{"label": b.label, "start_time": "13:00", "end_time": "15:00"} for b in context.busy_windows]}


def request(app, path, body=None, *, headers=None, host="127.0.0.1", client="127.0.0.1", method=None):
    async def call():
        transport = httpx.ASGITransport(app=app, client=(client, 12345), raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url=f"http://{host}:8001") as connection:
            return await connection.request(method or ("GET" if body is None else "POST"), path,
                                            json=body, headers=HEADERS if headers is None else headers)
    return asyncio.run(call())


@pytest.fixture
def transport(monkeypatch):
    instances = []
    def install(*responses):
        calls = []
        def handler(req):
            calls.append(req)
            assert len(calls) <= len(responses) <= 2
            import json
            payload = json.loads(req.content)
            assert payload["model"] == "muse-spark-1.3"
            assert payload["max_completion_tokens"] == 2048
            assert payload["reasoning_effort"] == "low"
            assert req.extensions["timeout"] == {"connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0}
            value = responses[len(calls)-1]
            if isinstance(value, Exception): raise value
            if isinstance(value, httpx.Response): return value
            content = value.model_dump_json() if isinstance(value, ProposedPlan) else value
            return httpx.Response(200, json={"id": "offline-api", "object": "chat.completion", "created": 0,
                "model": "muse-spark-1.3", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content}}]})
        def construct(**kwargs):
            instance = MetaProvider(api_key=CANARY, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
            assert instance._client.max_retries == 0
            instances.append(instance)
            return instance
        monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
        monkeypatch.setattr(live, "MetaProvider", construct)
        return calls
    yield install
    assert all(i._client.is_closed() for i in instances)


def test_startup_health_and_preflight_never_load_credentials_or_request_model(app, monkeypatch):
    provider = Mock(side_effect=AssertionError("No model request on load"))
    monkeypatch.setattr(live, "MetaProvider", provider)
    for _ in range(2):
        assert request(app, "/api/health").json() == {"status": "ok", "live_enabled": False, "evidence": "muse"}
        response = request(app, "/api/validate", {"day": day_body()})
        assert response.status_code == 200 and response.json()["conflicts"] == []
        assert "not proof" in response.json()["message"]
        assert response.headers["cache-control"] == "no-store"
    provider.assert_not_called(); live.load_dotenv.assert_not_called()


@pytest.mark.parametrize("flag", [None, "0", "true", " 1", "1 "])
def test_live_gate_mandatory(app, monkeypatch, flag):
    if flag is not None: monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", flag)
    provider = Mock(); monkeypatch.setattr(live, "MetaProvider", provider)
    response = request(app, "/api/rescue", {"day": day_body(), "request_id": str(uuid4())})
    assert response.status_code == 403
    provider.assert_not_called(); live.load_dotenv.assert_not_called()


@pytest.mark.parametrize("mutation", ["duration", "duplicate", "name", "shortening", "timezone", "extra"])
def test_invalid_requests_rejected_without_echoing_input(app, mutation):
    body = day_body()
    if mutation == "duration": body["activities"][0]["duration_minutes"] = 0
    if mutation == "duplicate": body["activities"][1]["id"] = body["activities"][0]["id"]
    if mutation == "name": body["activities"][0]["title"] = ""
    if mutation == "shortening": body["activities"][1]["min_duration_minutes"] = 10
    if mutation == "timezone": body["now"] = "11:00:00+07:00"
    if mutation == "extra": body["MODEL_API_KEY"] = CANARY
    response = request(app, "/api/validate", {"day": body})
    assert response.status_code == 422
    assert CANARY not in response.text
    assert response.json()["code"] == "INVALID_INPUT"
    live.load_dotenv.assert_not_called()


def test_local_origin_host_and_explicit_action_boundary(app, monkeypatch):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    provider = Mock(); monkeypatch.setattr(live, "MetaProvider", provider)
    body = {"day": day_body(), "request_id": str(uuid4())}
    assert request(app, "/api/rescue", body, headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert request(app, "/api/rescue", body, headers={"Origin": ORIGINS[0]}).status_code == 400
    assert request(app, "/api/rescue", body, client="192.0.2.10").status_code == 403
    assert request(app, "/api/rescue", body, host="untrusted.invalid").status_code == 403
    response = request(app, "/api/rescue", method="OPTIONS", headers={"Origin": ORIGINS[0], "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-dayrescue-action"})
    assert response.status_code == 200 and response.headers["access-control-allow-origin"] == ORIGINS[0]
    provider.assert_not_called(); live.load_dotenv.assert_not_called()


@pytest.mark.parametrize("correction", [False, True])
def test_http_to_real_sdk_correction_and_fresh_acceptance(app, transport, correction):
    _, plan = unexpected_event()
    calls = transport(*([ProposedPlan(), plan] if correction else [plan]))
    body = day_body()
    response = request(app, "/api/rescue", {"day": body, "request_id": str(uuid4())})
    assert response.status_code == 200
    value = response.json()
    assert value["status"] == "valid" and value["validation"]["valid"]
    assert len(calls) == (2 if correction else 1)
    assert value["validation"]["kept_ids"] == ["call"]
    assert value["validation"]["moved_or_adjusted_ids"] == ["study"]
    assert CANARY not in response.text
    live.load_dotenv.assert_called_once()
    accepted = request(app, "/api/validate", {"day": body, "proposal": value["plan"], "fingerprint": value["fingerprint"]})
    assert accepted.json()["validation"]["valid"] and len(calls) == (2 if correction else 1)
    for changed in (dict(body, date="2026-11-05"), dict(body, revision=1)):
        assert request(app, "/api/validate", {"day": changed, "proposal": value["plan"], "fingerprint": value["fingerprint"]}).status_code == 409
    later = dict(body, now="17:00")
    stale_time = request(app, "/api/validate", {"day": later, "proposal": value["plan"], "fingerprint": value["fingerprint"]})
    assert stale_time.status_code == 200 and not stale_time.json()["validation"]["valid"]


def test_conflict_skips_credentials_and_model_even_when_enabled(app, monkeypatch):
    monkeypatch.setenv("DAYRESCUE_ENABLE_LIVE_AI", "1")
    provider = Mock(); monkeypatch.setattr(live, "MetaProvider", provider)
    body = day_body(); body["busy_windows"] = [{"label": "New appointment", "start_time": "16:00", "end_time": "17:00"}]
    response = request(app, "/api/rescue", {"day": body, "request_id": str(uuid4())})
    assert response.json()["status"] == "infeasible" and response.json()["plan"] is None
    assert response.json()["conflicts"][0]["code"] == "FIXED_BUSY_CONFLICT"
    provider.assert_not_called(); live.load_dotenv.assert_not_called()


@pytest.mark.parametrize("failure", [429, 500, "timeout", "malformed", "invalid"])
def test_failures_are_bounded_and_safe(app, transport, failure):
    value = (httpx.ReadTimeout(CANARY) if failure == "timeout" else CANARY if failure == "malformed"
             else ProposedPlan() if failure == "invalid" else httpx.Response(failure, json={"error": {"message": CANARY}}))
    calls = transport(*([value, value] if failure == "invalid" else [value]))
    response = request(app, "/api/rescue", {"day": day_body(), "request_id": str(uuid4())})
    assert response.status_code == 200 and response.json()["plan"] is None
    assert not response.json()["rationale"] and CANARY not in response.text
    assert len(calls) == (2 if failure == "invalid" else 1)
    if failure == "invalid": assert "does not prove" in response.json()["message"]


def test_request_id_replay_never_consumes_another_completion(app, transport):
    _, plan = unexpected_event(); calls = transport(plan)
    body = {"day": day_body(), "request_id": str(uuid4())}
    assert request(app, "/api/rescue", body).json()["status"] == "valid"
    assert request(app, "/api/rescue", body).status_code == 409
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["title", "duration", "priority", "fixed", "minimum", "busy", "window"])
def test_fingerprint_rejects_every_changed_input_even_without_revision_increment(app, field):
    original = day_body()
    fingerprint = request(app, "/api/validate", {"day": original}).json()["fingerprint"]
    changed = deepcopy(original)
    if field == "title": changed["activities"][0]["title"] = "Renamed"
    if field == "duration": changed["activities"][0]["duration_minutes"] = 60
    if field == "priority": changed["activities"][0]["priority"] = "high"
    if field == "fixed": changed["activities"][0]["fixed"] = True
    if field == "minimum": changed["activities"][0]["min_duration_minutes"] = 30
    if field == "busy": changed["busy_windows"][0]["end_time"] = "14:00"
    if field == "window": changed["day_end"] = "23:00"
    _, plan = unexpected_event()
    response = request(app, "/api/validate", {"day": changed, "proposal": plan.model_dump(), "fingerprint": fingerprint})
    assert response.status_code == 409
    live.load_dotenv.assert_not_called()


def test_oversized_and_non_json_input_never_reaches_the_model(app, monkeypatch):
    provider = Mock(); monkeypatch.setattr(live, "MetaProvider", provider)
    assert request(app, "/api/validate", {"day": day_body()}, headers={**HEADERS,"Content-Length":"65537"}).status_code == 413
    assert request(app, "/api/rescue", {"day": day_body()}, headers={**HEADERS,"Content-Type":"text/plain"}).status_code == 415
    provider.assert_not_called(); live.load_dotenv.assert_not_called()


def test_active_flexible_overlap_preserves_full_duration_and_uses_existing_validation(app, transport):
    _, plan = unexpected_event()
    calls = transport(plan)
    day = day_body(); day['now'] = '13:15'
    day['busy_windows'] = [{'label': 'Doorbell', 'start_time': '13:15', 'end_time': '13:45'}]
    preflight = request(app, '/api/validate', {'day': day})
    assert preflight.status_code == 200 and preflight.json()['conflicts'] == []
    response = request(app, '/api/rescue', {'day': day, 'request_id': str(uuid4())})
    assert response.json()['validation']['valid'] and len(calls) == 1
    import json
    sent = json.loads(json.loads(calls[0].content)['messages'][1]['content'])['context']
    assert sent['now_minute'] == 13 * 60 + 15
    assert sent['activities'][0]['duration_minutes'] == 90
    assert response.json()['plan']['scheduled'][0]['duration_minutes'] == 90
