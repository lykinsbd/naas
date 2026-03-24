"""Tests for send_command_structured resource."""

from base64 import b64encode
from unittest.mock import MagicMock, patch


class TestSendCommandStructured:
    def test_get(self, client):
        """Test GET returns base response."""
        response = client.get("/v1/send_command_structured")
        assert response.status_code == 200
        assert "app" in response.json

    def test_post_success(self, app, client):
        """Test POST enqueues structured job."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_job.meta = {}
        mock_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        app.config["q"].enqueue.return_value = mock_job

        with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
            with patch("naas.resources.send_command_structured.job_locker"):
                with patch("naas.resources.send_command_structured.emit_audit_event"):
                    response = client.post(
                        "/v1/send_command_structured",
                        json={
                            "ip": "192.168.1.1",
                            "commands": ["show version"],
                        },
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        assert response.json["job_id"] == "test-job-id"
        app.config["q"].enqueue.assert_called_once()

    def test_post_with_custom_template(self, app, client):
        """Test POST with custom TextFSM template."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_job.meta = {}
        mock_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        app.config["q"].enqueue.return_value = mock_job

        with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
            with patch("naas.resources.send_command_structured.job_locker"):
                with patch("naas.resources.send_command_structured.emit_audit_event"):
                    response = client.post(
                        "/v1/send_command_structured",
                        json={
                            "ip": "192.168.1.1",
                            "commands": ["show custom"],
                            "textfsm_template": "Value TEST (\\S+)\\n\\nStart\\n  ^${TEST}",
                        },
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        call_kwargs = app.config["q"].enqueue.call_args[1]
        assert call_kwargs["textfsm_template"] == "Value TEST (\\S+)\\n\\nStart\\n  ^${TEST}"

    def test_post_device_locked_out(self, app, client):
        """Test POST with locked out device returns 423."""
        auth = b64encode(b"testuser:testpass").decode()

        with patch("naas.resources.send_command_structured.device_lockout", return_value=True):
            response = client.post(
                "/v1/send_command_structured",
                json={
                    "ip": "192.168.1.1",
                    "commands": ["show version"],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 403

    def test_post_with_ttp_template(self, app, client):
        """Test POST with TTP template."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_job.meta = {}
        mock_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        app.config["q"].enqueue.return_value = mock_job

        with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
            with patch("naas.resources.send_command_structured.job_locker"):
                with patch("naas.resources.send_command_structured.emit_audit_event"):
                    response = client.post(
                        "/v1/send_command_structured",
                        json={
                            "ip": "192.168.1.1",
                            "commands": ["show interfaces"],
                            "ttp_template": "interface {{ interface }}",
                        },
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        call_kwargs = app.config["q"].enqueue.call_args[1]
        assert call_kwargs["ttp_template"] == "interface {{ interface }}"

    def test_post_with_tags(self, app, client):
        """Test POST with tags stores them in job meta."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        mock_job = MagicMock()
        mock_job.id = "test-job-id"
        mock_job.meta = {}
        mock_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        app.config["q"].enqueue.return_value = mock_job

        with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
            with patch("naas.resources.send_command_structured.job_locker"):
                with patch("naas.resources.send_command_structured.emit_audit_event"):
                    response = client.post(
                        "/v1/send_command_structured",
                        json={
                            "ip": "192.168.1.1",
                            "commands": ["show version"],
                            "tags": {"change": "CHG001"},
                        },
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        assert mock_job.meta["tags"] == {"change": "CHG001"}

    def test_post_textfsm_and_ttp_mutually_exclusive(self, app, client):
        """Test POST with both textfsm_template and ttp_template returns 422."""
        auth = b64encode(b"testuser:testpass").decode()

        response = client.post(
            "/v1/send_command_structured",
            json={
                "ip": "192.168.1.1",
                "commands": ["show version"],
                "textfsm_template": "Value TEST (\\S+)",
                "ttp_template": "interface {{ interface }}",
            },
            headers={"Authorization": f"Basic {auth}"},
        )

        assert response.status_code == 422

    def test_post_dedup_returns_existing_job(self, app, client):
        """POST returns existing job_id when duplicate structured job is in-flight."""
        from unittest.mock import MagicMock

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        dup_job = MagicMock()
        dup_job.id = "dup-structured-job"
        dup_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("naas.resources.send_command_structured.get_duplicate_job_id", return_value="dup-structured-job"):
            with patch("naas.resources.send_command_structured.RQJob.fetch", return_value=dup_job):
                with patch("naas.resources.send_command_structured.job_unlocker", return_value=True):
                    response = client.post(
                        "/v1/send_command_structured",
                        json={"ip": "192.168.1.1", "commands": ["show version"]},
                        headers={"Authorization": f"Basic {auth}"},
                    )

        assert response.status_code == 202
        assert response.json["deduplicated"] is True
        app.config["q"].enqueue.assert_not_called()

    def test_post_dedup_enqueues_new_when_job_gone(self, app, client):
        """POST enqueues new job when dedup key exists but job is gone."""
        from rq.exceptions import NoSuchJobError

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        app.config["q"].enqueue.return_value.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("naas.resources.send_command_structured.get_duplicate_job_id", return_value="gone-dup-id"):
            with patch("naas.resources.send_command_structured.RQJob.fetch", side_effect=NoSuchJobError):
                with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
                    with patch("naas.resources.send_command_structured.job_locker"):
                        with patch("naas.resources.send_command_structured.emit_audit_event"):
                            response = client.post(
                                "/v1/send_command_structured",
                                json={"ip": "192.168.1.1", "commands": ["show version"]},
                                headers={"Authorization": f"Basic {auth}"},
                            )

        assert response.status_code == 202
        assert response.json["deduplicated"] is False

    def test_post_idempotency_key_returns_existing(self, app, client):
        """POST with X-Idempotency-Key returns existing job on repeat."""
        from unittest.mock import MagicMock

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        existing_job = MagicMock()
        existing_job.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("naas.resources.send_command_structured.get_idempotent_job_id", return_value="existing-id"):
            with patch("naas.resources.send_command_structured.RQJob.fetch", return_value=existing_job):
                response = client.post(
                    "/v1/send_command_structured",
                    json={"ip": "192.168.1.1", "commands": ["show version"]},
                    headers={"Authorization": f"Basic {auth}", "X-Idempotency-Key": "my-key"},
                )

        assert response.status_code == 202
        assert response.json["idempotent"] is True

    def test_post_idempotency_key_enqueues_new_when_job_gone(self, app, client):
        """POST with X-Idempotency-Key enqueues new job if stored job is gone."""
        from rq.exceptions import NoSuchJobError

        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        app.config["q"].enqueue.return_value.enqueued_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("naas.resources.send_command_structured.get_idempotent_job_id", return_value="gone-id"):
            with patch("naas.resources.send_command_structured.RQJob.fetch", side_effect=NoSuchJobError):
                with patch("naas.resources.send_command_structured.device_lockout", return_value=False):
                    with patch("naas.resources.send_command_structured.job_locker"):
                        with patch("naas.resources.send_command_structured.emit_audit_event"):
                            response = client.post(
                                "/v1/send_command_structured",
                                json={"ip": "192.168.1.1", "commands": ["show version"]},
                                headers={"Authorization": f"Basic {auth}", "X-Idempotency-Key": "stale-key"},
                            )

        assert response.status_code == 202
        assert response.json["idempotent"] is False
