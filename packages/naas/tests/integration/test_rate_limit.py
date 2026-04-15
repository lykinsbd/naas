"""Integration tests for rate limiting."""

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CISSHGO_HOST = "240.11.2.100"
CISSHGO_PORT = 10022
API_AUTH = ("admin", "admin")
ADMIN_AUTH = ("admin", "integration-test-admin-secret")
API_URL = "https://localhost:18443"

PAYLOAD = {
    "host": CISSHGO_HOST,
    "port": CISSHGO_PORT,
    "platform": "cisco_ios",
    "commands": ["show version"],
    "username": "admin",
    "password": "admin",
}


class TestRateLimiting:
    """Rate limit integration tests.

    docker-compose.test.yml sets RATE_LIMIT_PER_CALLER_DEVICE=2, RATE_LIMIT_WINDOW=300.
    Basic auth users are exempt, so we use an API key (bearer) to test enforcement.
    """

    def _create_api_key(self):
        """Create an operator API key and return the token."""
        r = requests.post(
            f"{API_URL}/v2/api-keys",
            json={"name": "rate-limit-test", "role": "operator"},
            auth=ADMIN_AUTH,
            verify=False,
        )
        assert r.status_code == 201, f"API key creation failed: {r.status_code} {r.text}"
        return r.json()["token"]

    def test_per_device_limit_returns_429(self):
        """Third request to the same device within the window returns 429."""
        token = self._create_api_key()
        headers = {"Authorization": f"Bearer {token}"}

        # First two should succeed (202)
        for i in range(2):
            r = requests.post(f"{API_URL}/v2/send-command", json=PAYLOAD, headers=headers, verify=False)
            assert r.status_code == 202, f"Request {i + 1} failed: {r.status_code} {r.text}"

        # Third should be rate-limited (429)
        r = requests.post(f"{API_URL}/v2/send-command", json=PAYLOAD, headers=headers, verify=False)
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert r.json()["error"] == "Rate limit exceeded"

    def test_rate_limit_headers_present(self):
        """Successful responses include X-RateLimit-* headers."""
        token = self._create_api_key()
        headers = {"Authorization": f"Bearer {token}"}

        r = requests.post(f"{API_URL}/v2/send-command", json=PAYLOAD, headers=headers, verify=False)
        assert r.status_code == 202
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert "X-RateLimit-Reset" in r.headers
