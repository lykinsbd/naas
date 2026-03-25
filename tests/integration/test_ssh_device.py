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
    for _ in range(60):
        try:
            r = requests.get(f"{api_url}/healthcheck", verify=False, timeout=2)
            if r.status_code == 200:
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.fail("API did not become ready in 60s")


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

    def test_wrong_password_job_fails(self, api_url, wait_for_api, wait_for_cisshgo, redis_client):
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

        # Cleanup: clear user lockout so subsequent tests using the same user aren't blocked
        redis_client.delete(f"naas_failures_{CISSHGO_USER}")


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


# ---------------------------------------------------------------------------
# Host field (v1.4 - hostname support, ip deprecation)
# ---------------------------------------------------------------------------


class TestHostField:
    """Tests for the new 'host' field and deprecated 'ip' field."""

    def test_host_field_with_ip(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job submitted with 'host' field (IP) succeeds."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "finished"
        assert result["results"] is not None

    def test_deprecated_ip_field_still_works(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job submitted with deprecated 'ip' field still succeeds (backwards compat)."""
        payload = {
            "ip": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "finished"
        assert result["results"] is not None


# ---------------------------------------------------------------------------
# Job metadata in enqueue response (v1.4)
# ---------------------------------------------------------------------------


class TestEnqueueResponseMetadata:
    """Tests for queue_position, enqueued_at, timeout in enqueue response."""

    def test_enqueue_response_includes_metadata(self, api_url, wait_for_api, wait_for_cisshgo):
        """Enqueue response includes queue_position, enqueued_at, and timeout."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        r = requests.post(f"{api_url}/v1/send_command", json=payload, auth=API_AUTH, verify=False)
        assert r.status_code == 202
        data = r.json()
        assert "queue_position" in data
        assert isinstance(data["queue_position"], int)
        assert data["queue_position"] >= 0
        assert "enqueued_at" in data
        assert "T" in data["enqueued_at"]  # ISO 8601
        assert "timeout" in data
        assert isinstance(data["timeout"], int)
        assert data["timeout"] > 0


# ---------------------------------------------------------------------------
# Structured output (v1.3 - TextFSM)
# ---------------------------------------------------------------------------


class TestStructuredOutput:
    """Tests for /v1/send_command_structured endpoint."""

    def test_structured_output_with_ntc_templates(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_command_structured returns parsed output via ntc-templates."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_command_structured")
        assert result["status"] == "finished"
        # ntc-templates parses show version into a list of dicts
        assert result["results"] is not None
        show_version_result = result["results"].get("show version")
        assert show_version_result is not None

    def test_structured_output_with_custom_ttp_template(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_command_structured with TTP template returns parsed output."""
        # Simple TTP template that captures the hostname from cisshgo output
        ttp_template = "hostname {{ hostname }}"
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
            "ttp_template": ttp_template,
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_command_structured")
        assert result["status"] == "finished"
        assert result["results"] is not None


# ---------------------------------------------------------------------------
# Context routing (v1.4)
# ---------------------------------------------------------------------------


class TestContextRouting:
    """Tests for context-aware job routing."""

    def test_default_context_routes_to_default_worker(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job with default context (or no context) is processed successfully."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
            "context": "default",
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "finished"
        assert result["results"] is not None

    def test_alt_context_routes_to_alt_worker(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job with 'alt' context is processed by the alt worker."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
            "context": "alt",
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "finished"
        assert result["results"] is not None

    def test_invalid_context_returns_400(self, api_url, wait_for_api):
        """Job with unknown context returns 400."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
            "context": "nonexistent-context",
        }
        r = requests.post(f"{api_url}/v1/send_command", json=payload, auth=API_AUTH, verify=False)
        assert r.status_code == 400

    def test_get_contexts_returns_configured_contexts(self, api_url, wait_for_api):
        """GET /v1/contexts returns both configured contexts."""
        r = requests.get(f"{api_url}/v1/contexts", auth=API_AUTH, verify=False)
        assert r.status_code == 200
        data = r.json()
        assert "contexts" in data
        context_names = {c["name"] for c in data["contexts"]}
        assert "default" in context_names
        assert "alt" in context_names
        # Both contexts should have at least 1 worker
        for ctx in data["contexts"]:
            assert ctx["workers"] >= 1, f"Context {ctx['name']} has no workers"


# ---------------------------------------------------------------------------
# Job cancellation (v1.2)
# ---------------------------------------------------------------------------


class TestJobCancellation:
    """Tests for DELETE /v1/jobs/{job_id} endpoint."""

    def test_cancel_queued_job(self, api_url, wait_for_api):
        """A queued job can be cancelled before it starts."""
        # Submit to a slow unreachable host so the job stays queued long enough to cancel
        payload = {
            "host": "192.0.2.253",
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        r = requests.post(f"{api_url}/v1/send_command", json=payload, auth=API_AUTH, verify=False)
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        # Cancel it
        cancel_r = requests.delete(f"{api_url}/v1/jobs/{job_id}", auth=API_AUTH, verify=False)
        assert cancel_r.status_code in (200, 204), f"Cancel failed: {cancel_r.text}"

    def test_cancel_nonexistent_job_returns_404(self, api_url, wait_for_api):
        """Cancelling a non-existent job returns 404."""
        r = requests.delete(
            f"{api_url}/v1/jobs/00000000-0000-0000-0000-000000000000",
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# List jobs (v1.1)
# ---------------------------------------------------------------------------


class TestListJobs:
    """Tests for GET /v1/jobs endpoint."""

    def test_list_jobs_returns_submitted_job(self, api_url, wait_for_api, wait_for_cisshgo):
        """Submitted job appears in finished job list after completion."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload)
        job_id = result["job_id"]
        assert result["status"] == "finished"

        # Job should appear in finished list
        list_r = requests.get(f"{api_url}/v1/jobs?status=finished", auth=API_AUTH, verify=False)
        assert list_r.status_code == 200
        data = list_r.json()
        assert "jobs" in data
        job_ids = [j["job_id"] for j in data["jobs"]]
        assert job_id in job_ids

    def test_list_jobs_pagination(self, api_url, wait_for_api):
        """List jobs respects per_page parameter."""
        r = requests.get(f"{api_url}/v1/jobs?per_page=1", auth=API_AUTH, verify=False)
        assert r.status_code == 200
        data = r.json()
        assert len(data["jobs"]) <= 1


# ---------------------------------------------------------------------------
# Platform autodetect (v1.3)
# ---------------------------------------------------------------------------


class TestPlatformAutodetect:
    """Tests for platform='autodetect' using SSHDetect."""

    def test_autodetect_identifies_cisshgo(self, api_url, wait_for_api, wait_for_cisshgo):
        """Autodetect successfully identifies cisshgo device type and runs command."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": "autodetect",
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload, timeout=60)
        assert result["status"] == "finished"
        assert result["results"] is not None
        # Autodetect should have identified the platform
        assert result.get("detected_platform") is not None


# ---------------------------------------------------------------------------
# send_config with context (v1.4)
# ---------------------------------------------------------------------------


class TestSendConfigContext:
    """Tests for send_config with context routing."""

    def test_send_config_default_context(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_config with default context routes to default worker."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "config": ["interface Loopback0", "description test"],
            "context": "default",
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_config")
        assert result["status"] == "finished"

    def test_send_config_alt_context(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_config with alt context routes to alt worker."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "config": ["interface Loopback0", "description test-alt"],
            "context": "alt",
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_config")
        assert result["status"] == "finished"


# ---------------------------------------------------------------------------
# send_command_structured with context (v1.3 + v1.4)
# ---------------------------------------------------------------------------


class TestStructuredOutputWithContext:
    """Tests for send_command_structured routed via context."""

    def test_structured_output_alt_context(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_command_structured with alt context routes to alt worker and returns parsed output."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
            "context": "alt",
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_command_structured")
        assert result["status"] == "finished"
        assert result["results"] is not None


# ---------------------------------------------------------------------------
# Host field with hostname (v1.4)
# ---------------------------------------------------------------------------


class TestHostnameResolution:
    """Tests for host field accepting a hostname (not just IP)."""

    def test_hostname_resolves_and_connects(self, api_url, wait_for_api, wait_for_cisshgo):
        """Job submitted with hostname resolves via DNS and connects successfully."""
        payload = {
            "host": "cisshgo",  # Docker network hostname for cisshgo container
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "commands": ["show version"],
        }
        result = _submit_and_poll(api_url, payload)
        assert result["status"] == "finished"
        assert result["results"] is not None


# ---------------------------------------------------------------------------
# send_config result structure (v1.0)
# ---------------------------------------------------------------------------


class TestSendConfigResult:
    """Tests for send_config job result structure."""

    def test_send_config_result_structure(self, api_url, wait_for_api, wait_for_cisshgo):
        """send_config result contains expected fields."""
        payload = {
            "host": CISSHGO_HOST,
            "platform": CISSHGO_PLATFORM,
            "port": CISSHGO_PORT,
            "config": ["interface Loopback0", "description integration-test"],
        }
        result = _submit_and_poll(api_url, payload, endpoint="send_config")
        assert result["status"] == "finished"
        assert "job_id" in result
        assert "status" in result
        # send_config returns results as a string (config output) or None
        # Either is valid — the key assertion is the job completed without error
        assert result.get("error") is None
