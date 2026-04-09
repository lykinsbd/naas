"""Integration tests for API key authentication."""

import time

import jwt
import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JWT_SECRET = "integration-test-jwt-secret"
CISSHGO_HOST = "240.11.2.100"
ADMIN_AUTH = ("admin", "integration-test-admin-secret")


@pytest.fixture(scope="session")
def api_url():
    return "https://localhost:18443"


class TestApiKeyLifecycle:
    """Test create → use → list → revoke → reject flow against live stack."""

    def test_create_and_use_api_key(self, api_url):
        """Create a key, use it to send a command, verify it works."""
        # Create (requires Basic auth)
        resp = requests.post(f"{api_url}/v1/api-keys", json={"role": "admin"}, auth=ADMIN_AUTH, verify=False)
        assert resp.status_code == 201
        data = resp.json()
        assert data["key_id"].startswith("k-")
        token = data["token"]

        # Use it to send a command
        resp = requests.post(
            f"{api_url}/v1/send_command",
            json={
                "host": CISSHGO_HOST,
                "port": 10022,
                "platform": "cisco_ios",
                "commands": ["show version"],
                "username": "admin",
                "password": "admin",
            },
            headers={"Authorization": f"Bearer {token}"},
            verify=False,
        )
        assert resp.status_code == 202

    def test_list_keys(self, api_url):
        """List endpoint returns metadata for created keys."""
        create_resp = requests.post(
            f"{api_url}/v1/api-keys", json={"role": "operator", "contexts": ["dc1"]}, auth=ADMIN_AUTH, verify=False
        )
        key_id = create_resp.json()["key_id"]

        resp = requests.get(f"{api_url}/v1/api-keys", auth=ADMIN_AUTH, verify=False)
        assert resp.status_code == 200
        keys = resp.json()["keys"]
        match = [k for k in keys if k["key_id"] == key_id]
        assert len(match) == 1
        assert match[0]["role"] == "operator"

    def test_revoke_then_reject(self, api_url):
        """Revoked key should be rejected on subsequent use."""
        create_resp = requests.post(f"{api_url}/v1/api-keys", json={}, auth=ADMIN_AUTH, verify=False)
        key_id = create_resp.json()["key_id"]
        token = create_resp.json()["token"]

        # Revoke
        resp = requests.delete(f"{api_url}/v1/api-keys/{key_id}", auth=ADMIN_AUTH, verify=False)
        assert resp.status_code == 204

        # Attempt to use revoked key
        resp = requests.post(
            f"{api_url}/v1/send_command",
            json={
                "host": CISSHGO_HOST,
                "commands": ["show version"],
                "username": "admin",
                "password": "admin",
            },
            headers={"Authorization": f"Bearer {token}"},
            verify=False,
        )
        assert resp.status_code == 401

    def test_invalid_token_rejected(self, api_url):
        """A token signed with the wrong secret should be rejected."""
        fake_token = jwt.encode({"sub": "k-fake", "iat": int(time.time())}, "wrong-secret", algorithm="HS256")
        resp = requests.post(
            f"{api_url}/v1/send_command",
            json={
                "host": CISSHGO_HOST,
                "commands": ["show version"],
                "username": "admin",
                "password": "admin",
            },
            headers={"Authorization": f"Bearer {fake_token}"},
            verify=False,
        )
        assert resp.status_code == 401

    def test_bearer_missing_body_creds_rejected(self, api_url):
        """Bearer auth without username/password in body should fail."""
        create_resp = requests.post(f"{api_url}/v1/api-keys", json={}, auth=ADMIN_AUTH, verify=False)
        token = create_resp.json()["token"]

        resp = requests.post(
            f"{api_url}/v1/send_command",
            json={"host": CISSHGO_HOST, "commands": ["show version"]},
            headers={"Authorization": f"Bearer {token}"},
            verify=False,
        )
        assert resp.status_code == 422
