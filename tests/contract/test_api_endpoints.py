"""Contract tests for NAAS API endpoints.

These tests verify the API contract - request/response schemas, status codes,
and error handling - without requiring actual network devices or Docker.

Note: These tests should be run independently from other test suites due to
mocking requirements. Run with: pytest tests/contract
"""

import base64

import pytest


@pytest.fixture(scope="module")
def app(mock_redis, mock_rq_queue):
    """Get Flask app for testing."""
    from naas.app import app

    app.config["TESTING"] = True
    app.config["q"] = mock_rq_queue
    return app


@pytest.fixture(scope="module")
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Basic auth headers for testing."""
    credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
    # Use a unique request ID for each test
    import uuid

    return {
        "Authorization": f"Basic {credentials}",
        "X-Request-ID": str(uuid.uuid4()),
    }


class TestHealthcheck:
    """Test /healthcheck endpoint contract."""

    def test_healthcheck_returns_200(self, client):
        """Healthcheck should return 200 OK."""
        response = client.get("/healthcheck")
        assert response.status_code == 200

    def test_healthcheck_response_schema(self, client):
        """Healthcheck should return expected JSON schema."""
        response = client.get("/healthcheck")
        data = response.get_json()

        assert "status" in data
        assert "app" in data
        assert "version" in data
        assert data["status"] == "OK"
        assert data["app"] == "naas"
        assert isinstance(data["version"], str)


class TestSendCommand:
    """Test /send_command endpoint contract."""

    def test_get_returns_base_response(self, client):
        """GET /send_command should return base response."""
        response = client.get("/send_command")
        assert response.status_code == 200
        data = response.get_json()
        assert "app" in data
        assert "version" in data

    def test_post_requires_auth(self, client):
        """POST /send_command without auth should return 401."""
        payload = {
            "ip": "192.0.2.1",
            "commands": ["show version"],
        }
        response = client.post("/send_command", json=payload)
        assert response.status_code == 401

    def test_post_requires_json(self, client, auth_headers):
        """POST /send_command without JSON should return 415."""
        response = client.post("/send_command", headers=auth_headers)
        assert response.status_code == 415

    def test_post_requires_ip(self, client, auth_headers):
        """POST /send_command without ip should return 422."""
        payload = {"commands": ["show version"]}
        response = client.post("/send_command", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_post_requires_valid_ip(self, client, auth_headers):
        """POST /send_command with invalid ip should return 422."""
        payload = {
            "ip": "not-an-ip",
            "commands": ["show version"],
        }
        response = client.post("/send_command", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_post_requires_commands(self, client, auth_headers):
        """POST /send_command without commands should return 422."""
        payload = {"ip": "192.0.2.1"}
        response = client.post("/send_command", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_post_requires_commands_list(self, client, auth_headers):
        """POST /send_command with non-list commands should return 422."""
        payload = {
            "ip": "192.0.2.1",
            "commands": "show version",
        }
        response = client.post("/send_command", json=payload, headers=auth_headers)
        assert response.status_code == 422

    # Note: Tests for successful job creation (202 responses) require a fully
    # functional RQ queue which is complex to mock in contract tests.
    # These scenarios are covered by integration tests.


class TestSendConfig:
    """Test /send_config endpoint contract."""

    def test_get_returns_base_response(self, client):
        """GET /send_config should return base response."""
        response = client.get("/send_config")
        assert response.status_code == 200
        data = response.get_json()
        assert "app" in data
        assert "version" in data

    def test_post_requires_auth(self, client):
        """POST /send_config without auth should return 401."""
        payload = {
            "ip": "192.0.2.1",
            "commands": ["interface Ethernet1", "description Test"],
        }
        response = client.post("/send_config", json=payload)
        assert response.status_code == 401

    def test_post_requires_json(self, client, auth_headers):
        """POST /send_config without JSON should return 415."""
        response = client.post("/send_config", headers=auth_headers)
        assert response.status_code == 415

    def test_post_requires_ip(self, client, auth_headers):
        """POST /send_config without ip should return 422."""
        payload = {"commands": ["interface Ethernet1"]}
        response = client.post("/send_config", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_post_requires_commands(self, client, auth_headers):
        """POST /send_config without commands should return 422."""
        payload = {"ip": "192.0.2.1"}
        response = client.post("/send_config", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_post_rejects_save_config_non_bool(self, client, auth_headers):
        """POST /send_config should reject save_config as non-bool."""
        payload = {
            "ip": "192.0.2.1",
            "commands": ["interface Ethernet1"],
            "save_config": "yes",
        }
        response = client.post("/send_config", json=payload, headers=auth_headers)
        assert response.status_code == 422

    # Note: Tests for successful job creation (202 responses) require a fully
    # functional RQ queue which is complex to mock in contract tests.
    # These scenarios are covered by integration tests.


class TestGetResults:
    """Test /send_command/<job_id> and /send_config/<job_id> endpoint contract."""

    def test_get_requires_auth(self, client):
        """GET /send_command/<job_id> without auth should return 401."""
        job_id = "12345678-1234-1234-1234-123456789abc"
        response = client.get(f"/send_command/{job_id}")
        assert response.status_code == 401

    def test_get_requires_valid_uuid(self, client, auth_headers):
        """GET /send_command/<job_id> with invalid UUID should return 400."""
        response = client.get("/send_command/not-a-uuid", headers=auth_headers)
        assert response.status_code == 400

    def test_get_wrong_credentials_returns_403(self, client, auth_headers):
        """GET /send_command/<job_id> with wrong credentials should return 403."""
        # This job_id won't match the auth_headers credentials
        job_id = "12345678-1234-4234-8234-123456789abc"
        response = client.get(f"/send_command/{job_id}", headers=auth_headers)
        assert response.status_code == 403

    def test_get_response_schema_forbidden(self, client, auth_headers):
        """GET /send_command/<job_id> should return expected schema for forbidden."""
        job_id = "12345678-1234-4234-8234-123456789abc"
        response = client.get(f"/send_command/{job_id}", headers=auth_headers)
        data = response.get_json()

        assert "status" in data
        assert "error" in data
        assert "app" in data
        assert "version" in data
        assert data["status"] == 403
