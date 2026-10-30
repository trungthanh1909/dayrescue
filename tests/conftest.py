"""All automated checks are offline, regardless of the launching shell's opt-in."""

import socket

import httpx
import pytest
import requests


@pytest.fixture(autouse=True)
def offline_test_environment(monkeypatch):
    monkeypatch.delenv("DAYRESCUE_ENABLE_LIVE_AI", raising=False)

    def blocked(*args, **kwargs):
        pytest.fail("Real HTTP/external sockets are forbidden in automated tests")

    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        # Windows asyncio's internal wakeup socketpair used by Streamlit AppTest.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        blocked()

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
