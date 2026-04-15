"""Integration test for structured error codes."""

import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_AUTH = ("admin", "admin")
API_URL = "https://localhost:18443"


class TestStructuredErrorCodes:
    def test_connection_timeout_returns_error_code(self):
        """Unreachable host returns CONNECTION_TIMEOUT error code."""
        r = requests.post(
            f"{API_URL}/v2/send-command",
            json={
                "host": "192.0.2.1",
                "port": 22,
                "platform": "cisco_ios",
                "commands": ["show version"],
                "username": "admin",
                "password": "admin",
            },
            auth=API_AUTH,
            verify=False,
        )
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        # Poll until finished
        for _ in range(30):
            time.sleep(1)
            result = requests.get(
                f"{API_URL}/v1/send_command/{job_id}",
                auth=API_AUTH,
                verify=False,
            )
            if result.json()["status"] in ("finished", "failed"):
                break

        data = result.json()
        assert data["error"] is not None
        assert data["error_code"] == "CONNECTION_TIMEOUT"
        assert data["error_retryable"] is True
