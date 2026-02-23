"""Unit tests for API resource endpoints."""

from naas import __version__


class TestHealthCheck:
    """Tests for the /healthcheck endpoint."""

    def test_get_returns_200(self, client):
        """Healthcheck should return 200 OK."""
        response = client.get("/healthcheck")
        assert response.status_code == 200

    def test_get_returns_json(self, client):
        """Healthcheck should return JSON response."""
        response = client.get("/healthcheck")
        assert response.content_type == "application/json"

    def test_get_response_structure(self, client):
        """Healthcheck should return status, app, and version."""
        response = client.get("/healthcheck")
        data = response.get_json()
        assert "status" in data
        assert "app" in data
        assert "version" in data

    def test_get_response_values(self, client):
        """Healthcheck should return correct values."""
        response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "OK"
        assert data["app"] == "naas"
        assert data["version"] == __version__
