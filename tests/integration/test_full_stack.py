"""Integration tests for NAAS full stack using Docker Compose."""

import time

import pytest
import requests
import urllib3

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture(scope="session")
def api_url():
    """Base URL for NAAS API."""
    return "https://localhost:18443"


@pytest.fixture(scope="session")
def wait_for_api(api_url):
    """Wait for API to be ready (session-scoped, runs once)."""
    max_retries = 15
    retry_delay = 1
    for i in range(max_retries):
        try:
            response = requests.get(f"{api_url}/healthcheck", verify=False, timeout=3)
            if response.status_code == 200:
                print(f"\n✓ API ready after {i * retry_delay}s")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(retry_delay)
    pytest.fail(f"API did not become ready in {max_retries * retry_delay}s")


def test_healthcheck(api_url, wait_for_api):
    """Test that healthcheck endpoint returns 200."""
    response = requests.get(f"{api_url}/healthcheck", verify=False)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_send_command_job_creation(api_url, wait_for_api):
    """Test creating a send_command job returns 401 without auth."""
    payload = {
        "platform": "cisco_ios",
        "host": "192.0.2.1",
        "username": "test",
        "password": "test",
        "command": "show version",
    }
    response = requests.post(f"{api_url}/send_command", json=payload, verify=False)
    # Without authentication, should get 401
    assert response.status_code == 401


def test_get_results_not_found(api_url, wait_for_api):
    """Test getting results for non-existent job returns 400 (bad request format)."""
    response = requests.get(f"{api_url}/send_command/nonexistent", verify=False)
    # Invalid job ID format returns 400
    assert response.status_code == 400
