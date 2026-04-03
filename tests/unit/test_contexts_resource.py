"""Unit tests for GET /v1/contexts endpoint."""

from unittest.mock import MagicMock, patch


class TestContexts:
    def test_get_contexts(self, client):
        """GET /v1/contexts returns list of configured contexts with worker counts."""
        mock_worker = MagicMock()
        mock_worker.queue_names.return_value = ["naas-default"]

        with patch("naas.resources.contexts.Worker.all", return_value=[mock_worker]):
            with patch("naas.resources.contexts.Queue") as mock_queue_cls:
                mock_queue_cls.return_value.__len__ = lambda self: 3
                response = client.get("/v1/contexts")

        assert response.status_code == 200
        data = response.get_json()
        assert "contexts" in data
        assert any(c["name"] == "default" for c in data["contexts"])
        default_ctx = next(c for c in data["contexts"] if c["name"] == "default")
        assert default_ctx["workers"] == 1
