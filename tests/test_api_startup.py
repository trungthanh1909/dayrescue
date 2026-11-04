"""Offline launcher diagnostics: never starts a real HTTP server or provider."""
from unittest.mock import Mock

from api import __main__ as launcher


def test_missing_api_dependency_explains_install_without_starting(monkeypatch, capsys):
    monkeypatch.setattr(launcher, 'find_spec', lambda package: None)
    import uvicorn
    run = Mock(); monkeypatch.setattr(uvicorn, 'run', run)
    assert launcher.main() == 1
    assert 'requirements-api.txt' in capsys.readouterr().err
    run.assert_not_called()


def test_port_startup_failure_explains_recovery_without_broadening_bind(monkeypatch, capsys):
    import uvicorn
    run = Mock(side_effect=SystemExit(1)); monkeypatch.setattr(uvicorn, 'run', run)
    assert launcher.main() == 1
    assert 'port 8001' in capsys.readouterr().err
    assert run.call_args.kwargs['host'] == '127.0.0.1'
    assert run.call_args.kwargs['proxy_headers'] is False
