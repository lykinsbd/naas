"""Unit tests for credential encryption."""

from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet, InvalidToken

from naas.library.auth import Credentials
from naas.library.encryption import decrypt_credentials, encrypt_credentials


@pytest.fixture()
def _mock_encryption_key(app):
    """Provide a Fernet key via mock secrets backend."""
    key = Fernet.generate_key().decode()
    mock_backend = MagicMock()
    mock_backend.get_secret.return_value = key
    app.config["secrets"] = mock_backend


@pytest.fixture(autouse=True)
def _reset_fernet_cache():
    """Reset cached MultiFernet between tests."""
    import naas.library.encryption as enc

    enc._fernet = None
    yield
    enc._fernet = None


@pytest.mark.usefixtures("_mock_encryption_key")
class TestCredentialEncryption:
    def test_round_trip(self, app):
        with app.app_context():
            creds = Credentials(username="admin", password="secret", enable="enable123")
            encrypted = encrypt_credentials(creds)
            assert isinstance(encrypted, bytes)
            assert b"admin" not in encrypted
            decrypted = decrypt_credentials(encrypted)
        assert decrypted.username == "admin"
        assert decrypted.password == "secret"
        assert decrypted.enable == "enable123"

    def test_wrong_key_fails(self, app):
        with app.app_context():
            creds = Credentials(username="admin", password="secret")
            encrypted = encrypt_credentials(creds)
        # Change the key
        import naas.library.encryption as enc

        enc._fernet = None
        new_key = Fernet.generate_key().decode()
        app.config["secrets"] = MagicMock()
        app.config["secrets"].get_secret.return_value = new_key
        with app.app_context():
            with pytest.raises(InvalidToken):
                decrypt_credentials(encrypted)

    def test_multifernet_rotation(self, app):
        """Old key can still decrypt after rotation."""
        old_key = Fernet.generate_key().decode()
        app.config["secrets"] = MagicMock()
        app.config["secrets"].get_secret.return_value = old_key
        import naas.library.encryption as enc

        enc._fernet = None
        with app.app_context():
            creds = Credentials(username="u", password="p")
            encrypted = encrypt_credentials(creds)

        # Rotate: new key first, old key second
        new_key = Fernet.generate_key().decode()
        app.config["secrets"].get_secret.return_value = f"{new_key},{old_key}"
        enc._fernet = None
        with app.app_context():
            decrypted = decrypt_credentials(encrypted)
        assert decrypted.username == "u"


@pytest.mark.usefixtures("_mock_encryption_key")
class TestEncryptionInValidPost:
    """Test that valid_post encrypts credentials when enabled."""

    def test_encrypted_credentials_passed_to_enqueue(self, app, client, monkeypatch):
        from base64 import b64encode

        from naas.library.encryption import decrypt_credentials

        monkeypatch.setattr("naas.config.CREDENTIAL_ENCRYPTION_ENABLED", True)
        auth = b64encode(b"testuser:testpass").decode()
        app.config["redis"].set("naas_cred_salt", b"test-salt")
        with app.app_context():
            response = client.post(
                "/v1/send_command",
                json={"host": "192.168.1.1", "commands": ["show version"]},
                headers={"Authorization": f"Basic {auth}"},
            )
        assert response.status_code == 202
        # Verify the enqueued credentials are bytes (encrypted)
        enqueue_call = app.config["q"].enqueue.call_args
        creds_arg = enqueue_call.kwargs["credentials"]
        assert isinstance(creds_arg, bytes)
        # Verify they decrypt correctly
        with app.app_context():
            decrypted = decrypt_credentials(creds_arg)
        assert decrypted.username == "testuser"
        assert decrypted.password == "testpass"


@pytest.mark.usefixtures("_mock_encryption_key")
class TestResolveCredentials:
    def test_resolve_decrypts_bytes(self, app):
        from naas.library.netmiko_lib import _resolve_credentials

        with app.app_context():
            creds = Credentials(username="u", password="p")
            encrypted = encrypt_credentials(creds)
            resolved = _resolve_credentials(encrypted)
        assert resolved.username == "u"

    def test_resolve_passes_through_credentials(self, app):
        from naas.library.netmiko_lib import _resolve_credentials

        creds = Credentials(username="u", password="p")
        resolved = _resolve_credentials(creds)
        assert resolved is creds


class TestFernetFallback:
    """Test _get_fernet falls back to env var outside Flask context."""

    def test_env_var_fallback(self, monkeypatch):
        import naas.library.encryption as enc

        enc._fernet = None
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("NAAS_ENCRYPTION_KEY", key)
        creds = Credentials(username="u", password="p")
        encrypted = enc.encrypt_credentials(creds)
        decrypted = enc.decrypt_credentials(encrypted)
        assert decrypted.username == "u"
        enc._fernet = None

    def test_missing_key_raises(self, app, monkeypatch):
        import naas.library.encryption as enc

        enc._fernet = None
        monkeypatch.delenv("NAAS_ENCRYPTION_KEY", raising=False)
        # Make secrets backend also fail
        mock_backend = MagicMock()
        mock_backend.get_secret.side_effect = KeyError("NAAS_ENCRYPTION_KEY")
        app.config["secrets"] = mock_backend
        with app.app_context():
            with pytest.raises(RuntimeError, match="NAAS_ENCRYPTION_KEY not available"):
                enc._get_fernet()
        enc._fernet = None
