"""Unit test configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def mock_device_lockout(monkeypatch):
    """Prevent device_lockout from connecting to Redis in unit tests."""
    monkeypatch.setattr("naas.library.auth.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.library.circuit_breaker.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.resources.send_command.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.resources.send_config.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.resources.send_command_structured.device_lockout", lambda **kwargs: False)


@pytest.fixture(autouse=True)
def mock_context_routing(monkeypatch, app):
    """Bypass context worker check — return the test app's mock queue directly."""
    import naas.library.worker_cache as wc

    # Reset worker cache between tests to prevent stale state
    wc._cache = []
    wc._cache_ts = 0.0

    q = app.config["q"]

    def mock_get_queue(context, redis):
        return q

    monkeypatch.setattr("naas.resources.send_command.get_queue_for_context", mock_get_queue)
    monkeypatch.setattr("naas.resources.send_command_structured.get_queue_for_context", mock_get_queue)
    monkeypatch.setattr("naas.resources.send_config.get_queue_for_context", mock_get_queue)
