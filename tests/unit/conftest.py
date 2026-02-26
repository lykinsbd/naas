"""Unit test configuration and shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def mock_device_lockout(monkeypatch):
    """Prevent device_lockout from connecting to Redis in unit tests."""
    monkeypatch.setattr("naas.library.auth.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.library.netmiko_lib.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.resources.send_command.device_lockout", lambda **kwargs: False)
    monkeypatch.setattr("naas.resources.send_config.device_lockout", lambda **kwargs: False)
