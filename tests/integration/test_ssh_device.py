"""Integration tests for NAAS SSH device interaction via cisshgo mock device."""

import time
import uuid

import pytest
import requests
import urllib3
from redis import Redis

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# cisshgo connection details — fixed IP assigned in docker-compose.test.yml
# so the NAAS API can accept it (ip field validates as IPv4 address)
CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022
CISSHGO_PLATFORM = "cisco_ios"
CISSHGO_USER = "admin"
CISSHGO_PASS = "admin"

# API auth (Basic Auth for NAAS itself — same creds passed through to device)
API_AUTH = (CISSHGO_USER, CISSHGO_PASS)


@pytest.fixture(scope="session")
def api_url():
    """Base URL for NAAS API."""
    return "https://localhost:18443"


@pytest.fixture(scope="session")
def redis_client():
    """Direct Redis connection for state manipulation between tests."""
    return Redis(host="localhost", port=16379, password="test_password", decode_responses=True)


@pytest.fixture(scope="session")
def wait_for_api(api_url):
    """Wait for API to be ready."""
    for _ in range(30):
        try:
            r = requests.get(f"{api_url}/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.fail("API did not become ready in 30s")


@pytest.fixture(scope="session")
def wait_for_cisshgo():
    """Wait for cisshgo SSH port to be ready."""
    import socket

    for _ in range(30):
        try:
            with socket.create_connection(("localhost", CISSHGO_PORT), timeout=2):
                return
        except OSError:
            pass
        time.sleep(1)
    pytest.fail("cisshgo did not become ready in 30s")


def _submit_and_poll(
    api_url: str,
    payload: dict,
    auth: tuple = API_AUTH,
    endpoint: str = "send_command",
    timeout: int = 30,
) -> dict:
    """Submit a job and poll until finished or failed. Returns final job result."""
    r = requests.post(
        f"{api_url}/v1/{endpoint}",
        json=payload,
        auth=auth,
        verify=False,
    )
    assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
    job_id = r.json()["job_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        result = requests.get(f"{api_url}/v1/{endpoint}/{job_id}", auth=auth, verify=False)
        assert result.status_code == 200
        data = result.json()
        if data["status"] in ("finished", "failed"):
            return data
        time.sleep(0.5)

    pytest.fail(f"Job {job_id} did not complete within {timeout}s")


def _device_payload(commands: list[str], ip: str = CISSHGO_HOST) -> dict:
    return {
        "ip": ip,
        "platform": CISSHGO_PLATFORM,
        "port": CISSHGO_PORT,
        "commands": commands,
    }


def _config_payload(config: list[str], ip: str = CISSHGO_HOST) -> dict:
    return {
        "ip": ip,
        "platform": CISSHGO_PLATFORM,
        "port": CISSHGO_PORT,
        "config": config,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSendCommandHappyPath:
    """send_command against real cisshgo SSH device."""

    def test_show_version(self, api_url, wait_for_api, wait_for_cisshgo):
        """Single command returns expected output."""
        result = _submit_and_poll(api_url, _device_payload(["show version"]))
        assert result["status"] == "finished"
        assert "Cisco IOS" in result["results"]["show version"]

    def test_multiple_commands(self, api_url, wait_for_api, wait_for_cisshgo):
        """Multiple commands all return output."""
        result = _submit_and_poll(
            api_url,
            _device_payload(["show version", "show ip interface brief"]),
        )
        assert result["status"] == "finished"
        assert "Cisco IOS" in result["results"]["show version"]
        assert "Interface" in result["results"]["show ip interface brief"]

    def test_show_running_config(self, api_url, wait_for_api, wait_for_cisshgo):
        """show running-config returns output."""
        result = _submit_and_poll(api_url, _device_payload(["show running-config"]))
        assert result["status"] == "finished"
        assert result["results"]["show running-config"]


class TestSendConfigHappyPath:
    """send_config against real cisshgo SSH device."""

    def test_send_config(self, api_url, wait_for_api, wait_for_cisshgo):
        """Config commands complete successfully."""
        result = _submit_and_poll(
            api_url,
            _config_payload(["interface Loopback0", "description test"]),
            endpoint="send_config",
        )
        assert result["status"] == "finished"


# ---------------------------------------------------------------------------
# Auth failure
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """Jobs with wrong device credentials fail cleanly."""

    def test_wrong_password_job_fails(self, api_url, wait_for_api, wait_for_cisshgo):
        """Wrong device password results in an auth error in the job result."""
        payload = {
            "ip": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        # Use wrong password — cisshgo validates credentials, so this will fail
        result = _submit_and_poll(api_url, payload, auth=(CISSHGO_USER, "wrongpassword"))
        assert result["status"] == "finished"
        assert result["results"] is None
        assert result.get("error")
        assert "Authentication" in result["error"]


# ---------------------------------------------------------------------------
# Device lockout
# ---------------------------------------------------------------------------


class TestDeviceLockout:
    """Device IP lockout triggers after 10 failures within 10 minutes."""

    def test_device_lockout_blocks_submission(self, api_url, wait_for_api, wait_for_cisshgo, redis_client):
        """After 10 failures for an IP, new jobs are rejected at the API level."""
        # Use a unique IP so we don't pollute other tests
        locked_ip = "192.0.2.1"
        lockout_key = f"naas_failures_device_{locked_ip}"

        # Seed 10 failure entries directly in Redis (sliding window uses sorted set)
        now = time.time()
        redis_client.delete(lockout_key)
        for i in range(10):
            redis_client.zadd(lockout_key, {str(uuid.uuid4()): now - i})
        redis_client.expire(lockout_key, 600)

        # Next submission should be rejected with 403
        payload = {
            "ip": locked_ip,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        r = requests.post(
            f"{api_url}/v1/send_command",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 403

        # Cleanup
        redis_client.delete(lockout_key)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Circuit breaker opens after CIRCUIT_BREAKER_THRESHOLD (5) failures."""

    def test_circuit_breaker_opens_and_fast_fails(self, api_url, wait_for_api, wait_for_cisshgo, redis_client):
        """After threshold failures, circuit opens and jobs fail without SSH attempt."""
        # Use a unique IP to isolate from other tests
        cb_ip = "192.0.2.2"
        # Key format matches RedisCircuitBreakerStorage: circuit_breaker:device_{ip}
        cb_key = f"circuit_breaker:device_{cb_ip}"

        # Seed circuit breaker state: open, counter at threshold
        redis_client.hset(
            cb_key,
            mapping={
                "state": "open",
                "counter": "5",
                "success_counter": "0",
                "opened_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

        payload = {
            "ip": cb_ip,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "failed"
        assert result.get("error")
        # Error should indicate circuit is open, not an SSH timeout
        assert "circuit" in result["error"].lower() or "open" in result["error"].lower()

        # Cleanup
        redis_client.delete(cb_key)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Edge cases and error scenarios."""

    def test_invalid_platform_fails(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job with unsupported platform is rejected at the API level with 422."""
        payload = {
            "ip": CISSHGO_HOST,
            "platform": "not_a_real_platform",
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        r = requests.post(
            f"{api_url}/v1/send_command",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )
        # Pydantic validates platform against Netmiko device types — invalid platform
        # is rejected before enqueueing, so we get 422 Unprocessable Entity
        assert r.status_code == 422

    def test_unreachable_host_fails(self, api_url, wait_for_api):
        """Job targeting unreachable host completes with connection error in result."""
        payload = {
            "ip": "192.0.2.254",  # TEST-NET, guaranteed unreachable
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload, timeout=60)
        # Worker catches the connection exception and returns it as an error;
        # job status is "finished" (worker ran to completion) but results is None
        assert result["results"] is None
        assert result.get("error")
        assert "TCP connection" in result["error"] or "timed out" in result["error"].lower()
