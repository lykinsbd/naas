"""Unit tests for API resource endpoints."""

from unittest.mock import patch

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
        """Healthcheck should return status, version, uptime, and components."""
        response = client.get("/healthcheck")
        data = response.get_json()
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "components" in data
        assert "redis" in data["components"]
        assert "queue" in data["components"]

    def test_get_response_values(self, client):
        """Healthcheck should return correct values when healthy."""
        response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__
        assert data["components"]["redis"]["status"] == "healthy"
        assert "depth" in data["components"]["queue"]

    def test_get_redis_unhealthy(self, app, client):
        """Healthcheck should return degraded when Redis is unreachable."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        with patch.object(app.config["redis"], "ping", side_effect=RedisConnectionError("connection refused")):
            response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"]["status"] == "unhealthy"
