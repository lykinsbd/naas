"""Integration tests for NAAS full stack using Docker Compose."""

import pytest
from naas_client import NaasClient
from naas_client.exceptions import NaasApiError
from naas_client.models import HealthCheckResponse


@pytest.fixture(scope="session")
def client(docker_compose):
    """NaasClient for full stack tests."""
    c = NaasClient("https://localhost:18443", username="admin", password="admin", verify=False)
    yield c
    c.close()


def test_healthcheck(client):
    """Test that healthcheck endpoint returns healthy."""
    health = client.healthcheck()
    assert isinstance(health, HealthCheckResponse)
    assert health.status in ("healthy", "degraded", "no_workers")


def test_send_command_no_auth():
    """Test that send_command without auth is rejected."""
    c = NaasClient("https://localhost:18443", verify=False)
    with pytest.raises(NaasApiError):
        c.send_command(
            platform="cisco_ios",
            host="192.0.2.1",
            username="test",
            password="test",
            commands=["show version"],
        )
    c.close()


def test_get_results_not_found(client):
    """Test getting results for non-existent job returns error."""
    with pytest.raises(NaasApiError):
        client.get_command_result("00000000-0000-0000-0000-000000000000")
