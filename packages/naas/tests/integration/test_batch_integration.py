"""Integration tests for batch/bulk operations endpoints.

Tests cover:
- POST /v2/send-command/batch — submit commands to multiple devices
- POST /v2/send-config/batch — submit config to multiple devices
- GET /v2/batches/{batch_id} — retrieve batch status

These tests require the docker-compose test stack to be running (cisshgo mock device,
Redis, NAAS API, and worker). They are invoked as part of the integration test suite
via the session-scoped `docker_compose` fixture in conftest.py.
"""

import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# cisshgo test device — fixed IP in docker-compose.test.yml network
CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022

# API connection details
API_URL = "https://localhost:18443"
API_AUTH = ("admin", "admin")
ADMIN_AUTH = ("admin", "integration-test-admin-secret")


def _create_operator_api_key(name: str = "batch-test") -> str:
    """Create an operator API key and return the Bearer token."""
    r = requests.post(
        f"{API_URL}/v2/api-keys",
        json={"name": name, "role": "operator"},
        auth=ADMIN_AUTH,
        verify=False,
    )
    assert r.status_code == 201, f"API key creation failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _create_viewer_api_key(name: str = "batch-viewer") -> str:
    """Create a viewer API key and return the Bearer token."""
    r = requests.post(
        f"{API_URL}/v2/api-keys",
        json={"name": name, "role": "viewer"},
        auth=ADMIN_AUTH,
        verify=False,
    )
    assert r.status_code == 201, f"API key creation failed: {r.status_code} {r.text}"
    return r.json()["token"]


class TestBatchSendCommand:
    """Tests for POST /v2/send-command/batch."""

    def test_submit_batch_returns_202_with_batch_id_and_job_ids(self):
        """Submit a batch with 2 devices and verify 202 response structure."""
        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )

        assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
        data = r.json()

        # Verify response structure
        assert "batch_id" in data
        assert "job_ids" in data
        assert "total" in data
        assert isinstance(data["batch_id"], str)
        assert len(data["batch_id"]) > 0
        assert isinstance(data["job_ids"], list)
        assert len(data["job_ids"]) == 2
        assert data["total"] == 2

        # Each job_id should be a valid UUID-like string
        for job_id in data["job_ids"]:
            assert isinstance(job_id, str)
            assert len(job_id) > 0

    def test_poll_batch_status_returns_valid_structure(self):
        """Submit a batch, then poll GET /v2/batches/{batch_id} and verify response."""
        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        # Submit batch
        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 202
        batch_id = r.json()["batch_id"]

        # Poll batch status
        r = requests.get(
            f"{API_URL}/v2/batches/{batch_id}",
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 200
        data = r.json()

        # Verify response structure
        assert data["batch_id"] == batch_id
        assert data["total"] == 2
        assert "completed" in data
        assert "pending" in data
        assert "failed" in data
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) == 2

        # Verify each job entry has required fields
        for job in data["jobs"]:
            assert "job_id" in job
            assert "host" in job
            assert "status" in job
            assert job["host"] == CISSHGO_HOST
            assert job["status"] in ("queued", "started", "finished", "failed", "unknown")

        # Sum of completed + pending + failed should equal total
        assert data["completed"] + data["pending"] + data["failed"] == data["total"]

    def test_batch_jobs_complete_successfully(self):
        """Submit a batch and wait for all jobs to finish successfully."""
        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        # Submit batch
        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 202
        batch_id = r.json()["batch_id"]

        # Poll until all jobs complete (timeout 60s)
        deadline = time.time() + 60
        while time.time() < deadline:
            r = requests.get(
                f"{API_URL}/v2/batches/{batch_id}",
                auth=API_AUTH,
                verify=False,
            )
            assert r.status_code == 200
            data = r.json()
            if data["completed"] + data["failed"] == data["total"]:
                break
            time.sleep(1)
        else:
            raise AssertionError(
                f"Batch {batch_id} did not complete within 60s. "
                f"Status: completed={data['completed']}, pending={data['pending']}, failed={data['failed']}"
            )

        # All jobs should have finished (cisshgo always succeeds)
        assert data["completed"] == 2
        assert data["failed"] == 0


class TestBatchSendConfig:
    """Tests for POST /v2/send-config/batch."""

    def test_submit_config_batch_with_commit(self):
        """Submit a send-config batch with commit=True and verify 202 response."""
        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["interface Loopback99", "description batch-test"],
            "username": "admin",
            "password": "admin",
            "commit": True,
        }

        r = requests.post(
            f"{API_URL}/v2/send-config/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )

        assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
        data = r.json()

        # Verify response structure
        assert "batch_id" in data
        assert "job_ids" in data
        assert "total" in data
        assert len(data["job_ids"]) == 2
        assert data["total"] == 2

    def test_config_batch_completes_successfully(self):
        """Submit a send-config batch and wait for jobs to complete."""
        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["interface Loopback100", "description batch-config-test"],
            "username": "admin",
            "password": "admin",
            "commit": True,
            "save_config": True,
        }

        r = requests.post(
            f"{API_URL}/v2/send-config/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 202
        batch_id = r.json()["batch_id"]

        # Poll until complete
        deadline = time.time() + 60
        while time.time() < deadline:
            r = requests.get(
                f"{API_URL}/v2/batches/{batch_id}",
                auth=API_AUTH,
                verify=False,
            )
            assert r.status_code == 200
            data = r.json()
            if data["completed"] + data["failed"] == data["total"]:
                break
            time.sleep(1)
        else:
            raise AssertionError(f"Config batch {batch_id} did not complete within 60s")

        assert data["completed"] == 1
        assert data["failed"] == 0


class TestBatchValidation:
    """Tests for batch validation and error handling."""

    def test_exceeding_max_devices_returns_422(self):
        """Submitting more than BATCH_MAX_DEVICES (default 100) returns 422."""
        # Build a payload with 101 devices (exceeds default limit of 100)
        devices = [{"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT} for _ in range(101)]
        payload = {
            "devices": devices,
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )

        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_exceeding_max_devices_config_returns_422(self):
        """Submitting more than BATCH_MAX_DEVICES for send-config also returns 422."""
        devices = [{"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT} for _ in range(101)]
        payload = {
            "devices": devices,
            "commands": ["interface Loopback1", "description test"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-config/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )

        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_empty_devices_returns_422(self):
        """Submitting an empty devices list returns 422."""
        payload = {
            "devices": [],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            auth=API_AUTH,
            verify=False,
        )

        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


class TestBatchAccessControl:
    """Tests for batch ownership and access control."""

    def test_accessing_another_users_batch_returns_403(self):
        """A different user cannot access a batch they did not create."""
        # User A submits a batch via API key
        token_a = _create_operator_api_key(name="batch-user-a")
        headers_a = {"Authorization": f"Bearer {token_a}"}

        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            headers=headers_a,
            verify=False,
        )
        assert r.status_code == 202, f"Batch submit failed: {r.status_code} {r.text}"
        batch_id = r.json()["batch_id"]

        # User B tries to access User A's batch
        token_b = _create_operator_api_key(name="batch-user-b")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        r = requests.get(
            f"{API_URL}/v2/batches/{batch_id}",
            headers=headers_b,
            verify=False,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_batch_owner_can_access_own_batch(self):
        """The user who created a batch can access it."""
        token = _create_operator_api_key(name="batch-owner-test")
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "devices": [
                {"host": CISSHGO_HOST, "platform": "cisco_ios", "port": CISSHGO_PORT},
            ],
            "commands": ["show version"],
            "username": "admin",
            "password": "admin",
        }

        r = requests.post(
            f"{API_URL}/v2/send-command/batch",
            json=payload,
            headers=headers,
            verify=False,
        )
        assert r.status_code == 202
        batch_id = r.json()["batch_id"]

        # Same user can access their batch
        r = requests.get(
            f"{API_URL}/v2/batches/{batch_id}",
            headers=headers,
            verify=False,
        )
        assert r.status_code == 200
        assert r.json()["batch_id"] == batch_id

    def test_nonexistent_batch_returns_404(self):
        """Requesting a non-existent batch returns 404."""
        r = requests.get(
            f"{API_URL}/v2/batches/nonexistent-batch-id-12345",
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
