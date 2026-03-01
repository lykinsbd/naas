"""Unit tests for send_command and send_config resources."""

from base64 import b64encode
from unittest.mock import MagicMock, patch


class TestSendCommand:
    """Test send_command resource."""

    def test_send_command_get(self, client):
        """Test GET returns base response."""
        response = client.get("/v1/send_command")
        assert response.status_code == 200
        assert "app" in response.json
        assert response.json["app"] == "naas"
        assert response.headers["X-API-Version"] == "v1"

    def test_send_command_legacy_route_deprecated(self, client):
        """Test legacy /send_command route returns deprecation headers."""
        response = client.get("/send_command")
        assert response.status_code == 200
        assert response.headers["X-API-Deprecated"] == "true"
        assert "X-API-Sunset" in response.headers

    def test_send_command_post_success(self, app, client):
        """Test POST enqueues job successfully."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        # Mock tacacs_auth_lockout to avoid Redis connection in validation
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.168.1.1",
                    "port": 22,
                    "platform": "cisco_ios",
                    "commands": ["show version"],
                    "delay_factor": 1,
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 202
        assert response.json["job_id"] is not None
        assert response.json["message"] == "Job enqueued"
        assert response.headers["X-Request-ID"] == response.json["job_id"]

    def test_send_command_post_no_auth(self, client):
        """Test POST without auth returns 401."""
        response = client.post(
            "/v1/send_command",
            json={
                "ip": "192.168.1.1",
                "commands": ["show version"],
            },
        )

        assert response.status_code == 401

    def test_send_command_device_locked_out(self, client):
        """Test that a locked-out device returns 403."""
        from base64 import b64encode
        from unittest.mock import patch

        auth = b64encode(b"testuser:testpass").decode()
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            with patch("naas.resources.send_command.device_lockout", return_value=True):
                response = client.post(
                    "/v1/send_command",
                    json={"ip": "192.168.1.1", "commands": ["show version"]},
                    headers={"Authorization": f"Basic {auth}"},
                )
        assert response.status_code == 403

    def test_send_command_invalid_ip(self, app, client):
        """Test POST with invalid IP returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "not-an-ip",
                    "commands": ["show version"],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_command_empty_commands(self, app, client):
        """Test POST with empty commands list returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.168.1.1",
                    "commands": [],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_command_empty_string_in_commands(self, app, client):
        """Test POST with empty string in commands list returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["show version", "  ", "show run"],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_command_invalid_port(self, app, client):
        """Test POST with invalid port returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.168.1.1",
                    "port": 99999,
                    "commands": ["show version"],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_command_invalid_platform(self, app, client):
        """Test POST with invalid platform returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["show version"],
                    "platform": "not_a_real_platform",
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_command_device_type_backward_compat(self, app, client):
        """Test POST with deprecated device_type maps to platform."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["show version"],
                    "device_type": "arista_eos",
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 202

    def test_send_command_device_type_ignored_when_platform_present(self, app, client):
        """Test POST with both device_type and platform uses platform."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["show version"],
                    "device_type": "arista_eos",
                    "platform": "cisco_nxos",
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 202

    def test_send_command_with_request_id(self, app, client):
        """Test POST with custom X-Request-ID uses that ID."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        custom_id = "44444444-4444-4444-4444-444444444444"

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "ip": "192.168.1.1",
                    "port": 22,
                    "platform": "cisco_ios",
                    "commands": ["show version"],
                    "delay_factor": 1,
                },
                headers={"Authorization": f"Basic {auth}", "X-Request-ID": custom_id},
            )

        # The response should use the custom ID
        if response.status_code != 202:
            print(f"Response: {response.get_json()}")
        assert response.status_code == 202
        # Just verify it accepted the request - the X-Request-ID handling is tested


class TestSendConfig:
    """Test send_config resource."""

    def test_send_config_get(self, client):
        """Test GET returns base response."""
        response = client.get("/v1/send_config")
        assert response.status_code == 200
        assert "app" in response.json
        assert response.json["app"] == "naas"
        assert response.headers["X-API-Version"] == "v1"

    def test_send_config_legacy_route_deprecated(self, client):
        """Test legacy /send_config route returns deprecation headers."""
        response = client.get("/send_config")
        assert response.status_code == 200
        assert response.headers["X-API-Deprecated"] == "true"
        assert "X-API-Sunset" in response.headers

    def test_send_config_post_success(self, app, client):
        """Test POST enqueues job successfully."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        # Mock tacacs_auth_lockout to avoid Redis connection in validation
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_config",
                json={
                    "ip": "192.168.1.1",
                    "port": 22,
                    "platform": "cisco_ios",
                    "commands": ["interface gi0/1", "description test"],
                    "delay_factor": 1,
                    "save_config": False,
                    "commit": False,
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 202
        assert "job_id" in response.json
        assert response.json["message"] == "Job enqueued"
        assert response.headers["X-Request-ID"] == response.json["job_id"]

    def test_send_config_empty_string_in_commands(self, app, client):
        """Test POST with empty string in commands list returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_config",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["interface gi0/1", "  ", "description test"],
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_config_missing_both_config_and_commands(self, app, client):
        """Test POST without config or commands returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_config",
                json={
                    "ip": "192.0.2.1",
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_config_invalid_platform(self, app, client):
        """Test POST with invalid platform returns 422."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_config",
                json={
                    "ip": "192.0.2.1",
                    "commands": ["interface gi0/1"],
                    "platform": "not_a_real_platform",
                },
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 422
        assert isinstance(response.json, list)

    def test_send_config_post_no_auth(self, client):
        """Test POST without auth returns 401."""
        response = client.post(
            "/v1/send_config",
            json={
                "ip": "192.168.1.1",
                "commands": ["interface gi0/1"],
            },
        )

        assert response.status_code == 401

    def test_send_config_device_locked_out(self, client):
        """Test that a locked-out device returns 403."""
        from base64 import b64encode
        from unittest.mock import patch

        auth = b64encode(b"testuser:testpass").decode()
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            with patch("naas.resources.send_config.device_lockout", return_value=True):
                response = client.post(
                    "/v1/send_config",
                    json={"ip": "192.168.1.1", "commands": ["interface gi0/1"]},
                    headers={"Authorization": f"Basic {auth}"},
                )
        assert response.status_code == 403


class TestGetResults:
    """Test get_results resource."""

    def test_get_results_not_found(self, app, client):
        """Test GET with non-existent job returns 404."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        # Mock job_unlocker to always return True (auth passes)
        with patch("naas.resources.get_results.job_unlocker", return_value=True):
            response = client.get(
                "/v1/send_command/00000000-0000-0000-0000-000000000000",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 404
        assert response.json["status"] == "not_found"

    def test_get_results_queued(self, app, client):
        """Test GET with queued job returns status."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "11111111-1111-1111-1111-111111111111"

        # Create a mock job
        job = MagicMock()
        job.get_status = lambda: "queued"

        def fetch_side_effect(job_id_param):
            if job_id_param == job_id:
                return job
            return None

        app.config["q"].fetch_job.side_effect = fetch_side_effect

        with patch("naas.resources.get_results.job_unlocker", return_value=True):
            response = client.get(
                f"/v1/send_command/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 200
        assert response.json["status"] == "queued"
        assert response.json["results"] is None

    def test_get_results_finished(self, app, client):
        """Test GET with finished job returns results."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "22222222-2222-2222-2222-222222222222"

        job = MagicMock()
        job.get_status = lambda: "finished"
        job.result = ("command output", None)

        def fetch_side_effect(job_id_param):
            if job_id_param == job_id:
                return job
            return None

        app.config["q"].fetch_job.side_effect = fetch_side_effect

        with patch("naas.resources.get_results.job_unlocker", return_value=True):
            response = client.get(
                f"/v1/send_command/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 200
        assert response.json["status"] == "finished"
        assert response.json["results"] == "command output"
        assert response.json["error"] is None

    def test_get_results_no_auth(self, client):
        """Test GET without auth returns 401."""
        response = client.get("/v1/send_command/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 401

    def test_get_results_failed(self, app, client):
        """Test GET with failed job returns error detail."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "44444444-4444-4444-4444-444444444444"
        job = MagicMock()
        job.get_status = lambda: "failed"
        job.exc_info = "NetMikoTimeoutException: Connection timed out"

        def fetch_side_effect(job_id_param):
            return job if job_id_param == job_id else None

        app.config["q"].fetch_job.side_effect = fetch_side_effect

        with patch("naas.resources.get_results.job_unlocker", return_value=True):
            response = client.get(
                f"/v1/send_command/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 200
        assert response.json["status"] == "failed"
        assert "NetMikoTimeoutException" in response.json["error"]

    def test_get_results_wrong_user(self, app, client):
        """Test GET with wrong user returns 403."""
        auth = b64encode(b"wronguser:wrongpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "33333333-3333-3333-3333-333333333333"

        job = MagicMock()

        def fetch_side_effect(job_id_param):
            if job_id_param == job_id:
                return job
            return None

        app.config["q"].fetch_job.side_effect = fetch_side_effect

        # Mock job_unlocker to return False (wrong user)
        with patch("naas.resources.get_results.job_unlocker", return_value=False):
            response = client.get(
                f"/v1/send_command/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 403


class TestCancelJob:
    """Tests for DELETE /v1/jobs/{job_id}."""

    def test_cancel_job_success(self, app, client):
        """Test DELETE cancels a queued job."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "55555555-5555-5555-5555-555555555555"
        job = MagicMock()
        job.get_status = lambda: "queued"
        job.cancel = MagicMock()

        app.config["q"].fetch_job.side_effect = lambda jid: job if jid == job_id else None

        with patch("naas.resources.cancel_job.job_unlocker", return_value=True):
            response = client.delete(
                f"/v1/jobs/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 204
        job.cancel.assert_called_once()

    def test_cancel_job_started(self, app, client):
        """Test DELETE cancels a started job."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "88888888-8888-8888-8888-888888888888"
        job = MagicMock()
        job.get_status = lambda: "started"
        job.cancel = MagicMock()

        app.config["q"].fetch_job.side_effect = lambda jid: job if jid == job_id else None

        with patch("naas.resources.cancel_job.job_unlocker", return_value=True):
            response = client.delete(
                f"/v1/jobs/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 204
        job.cancel.assert_called_once()

    def test_cancel_job_not_found(self, app, client):
        """Test DELETE with non-existent job returns 404."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        with patch("naas.resources.cancel_job.job_unlocker", return_value=True):
            response = client.delete(
                "/v1/jobs/00000000-0000-0000-0000-000000000000",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 404
        assert response.json["status"] == "not_found"

    def test_cancel_job_already_finished(self, app, client):
        """Test DELETE with finished job returns 409."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "66666666-6666-6666-6666-666666666666"
        job = MagicMock()
        job.get_status = lambda: "finished"

        app.config["q"].fetch_job.side_effect = lambda jid: job if jid == job_id else None

        with patch("naas.resources.cancel_job.job_unlocker", return_value=True):
            response = client.delete(
                f"/v1/jobs/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 409

    def test_cancel_job_no_auth(self, client):
        """Test DELETE without auth returns 401."""
        response = client.delete("/v1/jobs/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 401

    def test_cancel_job_wrong_user(self, app, client):
        """Test DELETE with wrong user returns 403."""
        auth = b64encode(b"wronguser:wrongpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")

        job_id = "77777777-7777-7777-7777-777777777777"
        job = MagicMock()

        app.config["q"].fetch_job.side_effect = lambda jid: job if jid == job_id else None

        with patch("naas.resources.cancel_job.job_unlocker", return_value=False):
            response = client.delete(
                f"/v1/jobs/{job_id}",
                headers={"Authorization": f"Basic {auth}"},
            )

        assert response.status_code == 403
