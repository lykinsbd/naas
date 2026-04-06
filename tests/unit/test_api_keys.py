"""Unit tests for API key authentication."""

import time
from base64 import b64encode
from unittest.mock import MagicMock, patch

import jwt
import pytest

from naas.library.api_keys import (
    KEY_META_PREFIX,
    REVOKED_KEYS_SET,
    create_api_key,
    list_api_keys,
    revoke_api_key,
    validate_api_key,
)

JWT_SECRET = "test-jwt-secret"


@pytest.fixture()
def _mock_secrets(app):
    """Inject a mock secrets backend that returns a known JWT secret."""
    mock_backend = MagicMock()
    mock_backend.get_secret.return_value = JWT_SECRET
    app.config["secrets"] = mock_backend


@pytest.mark.usefixtures("_mock_secrets")
class TestCreateApiKey:
    """Tests for create_api_key."""

    def test_creates_key_with_defaults(self, app):
        with app.app_context():
            result = create_api_key()
        assert result["key_id"].startswith("k-")
        assert result["role"] == "admin"
        assert result["contexts"] == ["*"]
        assert result["token"]
        assert result["expires_at"]

    def test_custom_role_and_contexts(self, app):
        with app.app_context():
            result = create_api_key(role="operator", contexts=["oob-dc1"])
        assert result["role"] == "operator"
        assert result["contexts"] == ["oob-dc1"]

    def test_no_expiry_when_ttl_zero(self, app):
        with app.app_context():
            result = create_api_key(ttl=0)
        assert result["expires_at"] == ""
        claims = jwt.decode(result["token"], JWT_SECRET, algorithms=["HS256"])
        assert "exp" not in claims

    def test_stores_metadata_in_redis(self, app):
        with app.app_context():
            result = create_api_key(created_by="admin-user")
            meta = app.config["redis"].hgetall(f"{KEY_META_PREFIX}{result['key_id']}")
        assert meta[b"role"] == b"admin"
        assert meta[b"created_by"] == b"admin-user"

    def test_max_ttl_caps_expiry(self, app, monkeypatch):
        monkeypatch.setattr("naas.library.api_keys.API_KEY_MAX_TTL", 60)
        with app.app_context():
            result = create_api_key(ttl=9999)
        claims = jwt.decode(result["token"], JWT_SECRET, algorithms=["HS256"])
        assert claims["exp"] - claims["iat"] == 60


@pytest.mark.usefixtures("_mock_secrets")
class TestValidateApiKey:
    """Tests for validate_api_key."""

    def test_valid_token(self, app):
        with app.app_context():
            token = create_api_key()["token"]
            claims = validate_api_key(token)
        assert claims["role"] == "admin"
        assert claims["sub"].startswith("k-")

    def test_expired_token_raises(self, app):
        with app.app_context():
            token = create_api_key(ttl=1)["token"]
        time.sleep(1.1)
        with app.app_context():
            with pytest.raises(jwt.ExpiredSignatureError):
                validate_api_key(token)

    def test_invalid_signature_raises(self, app):
        token = jwt.encode({"sub": "k-fake", "iat": int(time.time())}, "wrong-secret", algorithm="HS256")
        with app.app_context():
            with pytest.raises(jwt.InvalidSignatureError):
                validate_api_key(token)

    def test_revoked_token_raises(self, app):
        with app.app_context():
            result = create_api_key()
            app.config["redis"].sadd(REVOKED_KEYS_SET, result["key_id"])
            with pytest.raises(jwt.InvalidTokenError, match="revoked"):
                validate_api_key(result["token"])


@pytest.mark.usefixtures("_mock_secrets")
class TestRevokeApiKey:
    """Tests for revoke_api_key."""

    def test_revoke_existing_key(self, app):
        with app.app_context():
            key_id = create_api_key()["key_id"]
            assert revoke_api_key(key_id) is True
            assert app.config["redis"].sismember(REVOKED_KEYS_SET, key_id)
            assert not app.config["redis"].exists(f"{KEY_META_PREFIX}{key_id}")

    def test_revoke_nonexistent_key(self, app):
        with app.app_context():
            assert revoke_api_key("k-doesnotexist") is False


@pytest.mark.usefixtures("_mock_secrets")
class TestListApiKeys:
    """Tests for list_api_keys."""

    def test_list_returns_metadata(self, app):
        with app.app_context():
            key_id = create_api_key(role="operator", contexts=["dc1"], created_by="tester")["key_id"]
            keys = list_api_keys()
        match = [k for k in keys if k["key_id"] == key_id]
        assert len(match) == 1
        assert match[0]["role"] == "operator"
        assert match[0]["contexts"] == ["dc1"]
        assert match[0]["created_by"] == "tester"


@pytest.mark.usefixtures("_mock_secrets")
class TestApiKeysEndpoints:
    """Tests for /v1/api-keys resource endpoints."""

    _auth_header = {"Authorization": f"Basic {b64encode(b'admin:admin-secret').decode()}"}

    @pytest.fixture(autouse=True)
    def _set_admin_secret(self, monkeypatch):
        monkeypatch.setattr("naas.resources.api_keys.NAAS_ADMIN_SECRET", "admin-secret")

    def test_create_key_endpoint(self, app, client):
        with app.app_context():
            response = client.post("/v1/api-keys", json={"role": "operator"}, headers=self._auth_header)
        assert response.status_code == 201
        assert response.json["key_id"].startswith("k-")
        assert response.json["token"]
        assert response.json["role"] == "operator"

    def test_create_key_records_creator(self, app, client):
        with app.app_context():
            response = client.post("/v1/api-keys", json={}, headers=self._auth_header)
            keys = client.get("/v1/api-keys", headers=self._auth_header).json["keys"]
        match = [k for k in keys if k["key_id"] == response.json["key_id"]]
        assert match[0]["created_by"] == "admin"

    def test_list_keys_endpoint(self, app, client):
        with app.app_context():
            client.post("/v1/api-keys", json={}, headers=self._auth_header)
            response = client.get("/v1/api-keys", headers=self._auth_header)
        assert response.status_code == 200
        assert "keys" in response.json

    def test_revoke_key_endpoint(self, app, client):
        with app.app_context():
            key_id = client.post("/v1/api-keys", json={}, headers=self._auth_header).json["key_id"]
            response = client.delete(f"/v1/api-keys/{key_id}", headers=self._auth_header)
        assert response.status_code == 204

    def test_revoke_nonexistent_key_endpoint(self, app, client):
        with app.app_context():
            response = client.delete("/v1/api-keys/k-doesnotexist", headers=self._auth_header)
        assert response.status_code == 404

    def test_no_auth_returns_401(self, app, client):
        with app.app_context():
            assert client.post("/v1/api-keys", json={}).status_code == 401
            assert client.get("/v1/api-keys").status_code == 401
            assert client.delete("/v1/api-keys/k-x").status_code == 401

    def test_wrong_secret_returns_401(self, app, client):
        bad_auth = {"Authorization": f"Basic {b64encode(b'admin:wrong').decode()}"}
        with app.app_context():
            assert client.post("/v1/api-keys", json={}, headers=bad_auth).status_code == 401

    def test_unconfigured_secret_returns_401(self, app, client, monkeypatch):
        monkeypatch.setattr("naas.resources.api_keys.NAAS_ADMIN_SECRET", "")
        with app.app_context():
            assert client.post("/v1/api-keys", json={}, headers=self._auth_header).status_code == 401


@pytest.mark.usefixtures("_mock_secrets")
class TestBearerAuth:
    """Tests for Bearer JWT auth flow in valid_post."""

    def test_bearer_auth_with_body_creds(self, app, client):
        """Bearer JWT + body credentials should enqueue a job."""
        with app.app_context():
            token = create_api_key()["token"]
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={
                    "host": "192.168.1.1",
                    "commands": ["show version"],
                    "username": "netadmin",
                    "password": "secret",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 202

    def test_bearer_auth_missing_body_creds(self, app, client):
        """Bearer JWT without username/password in body should return 422."""
        with app.app_context():
            token = create_api_key()["token"]
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={"host": "192.168.1.1", "commands": ["show version"]},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 422

    def test_bearer_auth_invalid_token(self, client):
        """Invalid Bearer token should return 401."""
        response = client.post(
            "/v1/send_command",
            json={"host": "192.168.1.1", "commands": ["show version"]},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    def test_bearer_auth_skips_tacacs_lockout(self, app, client):
        """JWT-authenticated users should bypass TACACS lockout checks."""
        with app.app_context():
            token = create_api_key()["token"]
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        # Don't mock tacacs_auth_lockout — it should never be called for bearer
        response = client.post(
            "/v1/send_command",
            json={
                "host": "192.168.1.1",
                "commands": ["show version"],
                "username": "netadmin",
                "password": "secret",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202

    def test_basic_auth_still_works(self, app, client):
        """Basic auth should continue to work unchanged."""
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        with patch("naas.library.validation.tacacs_auth_lockout", return_value=False):
            response = client.post(
                "/v1/send_command",
                json={"host": "192.168.1.1", "commands": ["show version"]},
                headers={"Authorization": f"Basic {auth}"},
            )
        assert response.status_code == 202


@pytest.mark.usefixtures("_mock_secrets")
class TestRBAC:
    """Tests for role-based access control enforcement."""

    def _make_token(self, app, role):
        with app.app_context():
            return create_api_key(role=role)["token"]

    def test_viewer_cannot_send_command(self, app, client):
        token = self._make_token(app, "viewer")
        response = client.post(
            "/v1/send_command",
            json={"host": "192.168.1.1", "commands": ["show version"], "username": "u", "password": "p"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_viewer_cannot_send_config(self, app, client):
        token = self._make_token(app, "viewer")
        response = client.post(
            "/v1/send_config",
            json={"host": "192.168.1.1", "config": ["no shutdown"], "username": "u", "password": "p"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_operator_can_send_command(self, app, client):
        token = self._make_token(app, "operator")
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        response = client.post(
            "/v1/send_command",
            json={"host": "192.168.1.1", "commands": ["show version"], "username": "u", "password": "p"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202


@pytest.mark.usefixtures("_mock_secrets")
class TestContextAuthz:
    """Tests for context-based authorization."""

    def _make_token(self, app, contexts):
        with app.app_context():
            return create_api_key(role="operator", contexts=contexts)["token"]

    def test_wildcard_allows_any_context(self, app, client):
        token = self._make_token(app, ["*"])
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        response = client.post(
            "/v1/send_command",
            json={
                "host": "192.168.1.1",
                "commands": ["show version"],
                "username": "u",
                "password": "p",
                "context": "anything",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202

    def test_matching_context_allowed(self, app, client):
        token = self._make_token(app, ["oob-dc1"])
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        response = client.post(
            "/v1/send_command",
            json={
                "host": "192.168.1.1",
                "commands": ["show version"],
                "username": "u",
                "password": "p",
                "context": "oob-dc1",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202

    def test_wrong_context_forbidden(self, app, client):
        token = self._make_token(app, ["oob-dc1"])
        response = client.post(
            "/v1/send_command",
            json={
                "host": "192.168.1.1",
                "commands": ["show version"],
                "username": "u",
                "password": "p",
                "context": "prod",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_default_context_when_omitted(self, app, client):
        token = self._make_token(app, ["default"])
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        response = client.post(
            "/v1/send_command",
            json={"host": "192.168.1.1", "commands": ["show version"], "username": "u", "password": "p"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202
