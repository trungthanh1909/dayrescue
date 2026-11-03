"""TEST ONLY local browser harness. No real Meta transport or credentials.

Run explicitly with .venv/Scripts/python.exe tests/browser_api_fixture.py.
Uses the existing SDK and agent; one invalid hand-authored response, then a
fixed test proposal for Study Python 09:00/60/min30, Team check-in 10:00/30
Fixed, Read a chapter 11:00/30. No general scheduler is implemented here.
"""
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import httpx
    import requests
    import uvicorn
    from fastapi.responses import JSONResponse
    from api.app import create_app
    from core import live_generation as live
    from core.meta_client import MetaProvider
    from core.models import ProposedPlan

    os.environ['DAYRESCUE_ENABLE_LIVE_AI'] = '1'  # Test process only; transport forced below.
    os.environ.pop('MODEL_API_KEY', None)
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex
    def blocked(*args, **kwargs):
        raise RuntimeError('External networking is forbidden in this offline test harness')
    def guarded(method, sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
            return method(sock, address)
        return blocked()
    socket.socket.connect = lambda sock, address: guarded(connect, sock, address)
    socket.socket.connect_ex = lambda sock, address: guarded(connect_ex, sock, address)
    httpx.HTTPTransport.handle_request = blocked
    httpx.AsyncHTTPTransport.handle_async_request = blocked
    requests.Session.request = blocked

    def handler(request):
        body = json.loads(request.content)
        payload = json.loads(body['messages'][1]['content'])
        activities = {a['title']: a for a in payload['context']['activities']}
        expected = {'Study Python': (540, 60, False, 30), 'Team check-in': (600, 30, True, None), 'Read a chapter': (660, 30, False, None)}
        if set(activities) != set(expected):
            return httpx.Response(400, json={'error': {'message': 'Test fixture inputs do not match'}})
        for title, values in expected.items():
            a = activities[title]
            if (a['start_minute'], a['duration_minutes'], a['fixed'], a['min_duration_minutes']) != values:
                return httpx.Response(400, json={'error': {'message': 'Test fixture inputs do not match'}})
        print(f"OFFLINE MockTransport completion attempt={payload['attempt']}", flush=True)
        plan = ProposedPlan() if payload['attempt'] == 1 else ProposedPlan.model_validate({
            'scheduled': [{'activity_id': activities['Team check-in']['id'], 'start_minute': 600, 'duration_minutes': 30},
                          {'activity_id': activities['Study Python']['id'], 'start_minute': 630, 'duration_minutes': 30}],
            'postponed_ids': [activities['Read a chapter']['id']],
            'explanation': 'OFFLINE HAND-AUTHORED TEST FIXTURE, not Muse output. The check-in stays fixed; study moves and shortens to its permitted minimum; reading remains unscheduled. No optimality claim.'})
        return httpx.Response(200, json={'id': 'offline-browser', 'object': 'chat.completion', 'created': 0,
            'model': 'muse-spark-1.3', 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': plan.model_dump_json()}}]})

    def provider(**kwargs):
        return MetaProvider(api_key='offline-browser-test-only',
                            http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)

    app = create_app()
    @app.middleware('http')
    async def label_test_evidence(request, call_next):
        response = await call_next(request)
        if request.url.path in ('/api/health', '/api/rescue') and response.status_code == 200:
            raw = b''.join([chunk async for chunk in response.body_iterator])
            data = json.loads(raw); data['evidence'] = 'offline_fixture'
            return JSONResponse(data, status_code=response.status_code,
                                headers={'Cache-Control': 'no-store'})
        return response

    print('OFFLINE BROWSER TEST ONLY on 127.0.0.1:8001; no Meta requests, no .env reads.', flush=True)
    with patch.object(live, 'load_dotenv', Mock()), patch.object(live, 'MetaProvider', provider):
        uvicorn.run(app, host='127.0.0.1', port=8001, proxy_headers=False, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
