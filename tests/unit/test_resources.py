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
        assert "workers" in data["components"]

    def test_get_response_values_no_workers(self, client):
        """Healthcheck returns no_workers status when no RQ workers are running."""
        response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "no_workers"
        assert data["version"] == __version__
        assert data["components"]["redis"]["status"] == "healthy"
        assert data["components"]["workers"]["status"] == "no_workers"
        assert data["components"]["workers"]["count"] == 0

    def test_get_response_values_with_workers(self, client, monkeypatch):
        """Healthcheck returns healthy status when workers are present."""
        from unittest.mock import MagicMock

        mock_worker = MagicMock()
        mock_worker.get_current_job.return_value = None
        monkeypatch.setattr("naas.resources.healthcheck.Worker.all", lambda connection: [mock_worker])
        response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["components"]["workers"]["status"] == "healthy"
        assert data["components"]["workers"]["count"] == 1
        assert data["components"]["workers"]["active_jobs"] == 0

    def test_get_response_values_with_active_jobs(self, client, monkeypatch):
        """Healthcheck counts active jobs on workers."""
        from unittest.mock import MagicMock

        mock_worker = MagicMock()
        mock_worker.get_current_job.return_value = MagicMock()
        monkeypatch.setattr("naas.resources.healthcheck.Worker.all", lambda connection: [mock_worker])
        response = client.get("/healthcheck")
        data = response.get_json()
        assert data["components"]["workers"]["active_jobs"] == 1
        assert "depth" in data["components"]["queue"]

    def test_get_redis_unhealthy(self, app, client):
        """Healthcheck should return degraded when Redis is unreachable."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        with patch.object(app.config["redis"], "ping", side_effect=RedisConnectionError("connection refused")):
            response = client.get("/healthcheck")
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"]["status"] == "unhealthy"
