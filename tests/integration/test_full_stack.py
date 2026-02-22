"""Integration tests for NAAS full stack using Docker Compose."""

import time

import pytest
import requests
import urllib3

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture(scope="module")
def api_url():
    """Base URL for NAAS API."""
    return "https://localhost:8443"


@pytest.fixture(scope="module")
def wait_for_api(api_url):
    """Wait for API to be ready."""
    max_retries = 60  # Increased timeout
    retry_delay = 2
    for i in range(max_retries):
        try:
            response = requests.get(f"{api_url}/healthcheck", verify=False, timeout=5)
            if response.status_code == 200:
                print(f"\n✓ API ready after {i * retry_delay}s")
                return
        except requests.exceptions.RequestException as e:
            if i % 10 == 0:  # Log every 20 seconds
                print(f"\nWaiting for API... ({i * retry_delay}s) - {type(e).__name__}")
        time.sleep(retry_delay)
    pytest.fail(f"API did not become ready in {max_retries * retry_delay}s")


def test_healthcheck(api_url, wait_for_api):
    """Test that healthcheck endpoint returns 200."""
    response = requests.get(f"{api_url}/healthcheck", verify=False)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_send_command_job_creation(api_url, wait_for_api):
    """Test creating a send_command job."""
    payload = {
        "device_type": "cisco_ios",
        "host": "192.0.2.1",
        "username": "test",
        "password": "test",
        "command": "show version",
    }
    response = requests.post(f"{api_url}/send_command", json=payload, verify=False)
    assert response.status_code in [200, 201]
    data = response.json()
    assert "job_id" in data


def test_get_results_not_found(api_url, wait_for_api):
    """Test getting results for non-existent job."""
    response = requests.get(f"{api_url}/send_command/nonexistent", verify=False)
    assert response.status_code == 404
