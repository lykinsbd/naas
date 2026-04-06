"""Tests for naas.library.secrets module."""

from unittest.mock import MagicMock, patch

import pytest

from naas.library.secrets import EnvSecretsBackend, VaultSecretsBackend, get_secrets_backend


class TestEnvSecretsBackend:
    """Tests for EnvSecretsBackend."""

    def test_get_secret_returns_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "secret_value")
        backend = EnvSecretsBackend()
        assert backend.get_secret("MY_SECRET") == "secret_value"

    def test_get_secret_raises_key_error(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
        backend = EnvSecretsBackend()
        with pytest.raises(KeyError, match="not found in environment"):
            backend.get_secret("NONEXISTENT_SECRET")


class TestVaultSecretsBackend:
    """Tests for VaultSecretsBackend."""

    def test_init_raises_without_hvac(self):
        with patch.dict("sys.modules", {"hvac": None}):
            with pytest.raises(ImportError, match="hvac"):
                VaultSecretsBackend(url="https://vault:8200", token="test")

    def test_init_raises_on_auth_failure(self):
        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_hvac.Client.return_value = mock_client
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            with pytest.raises(RuntimeError, match="authentication failed"):
                VaultSecretsBackend(url="https://vault:8200", token="bad")

    def test_get_secret_returns_value(self):
        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {"MY_KEY": "my_value"}}}
        mock_hvac.Client.return_value = mock_client
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            backend = VaultSecretsBackend(url="https://vault:8200", token="test")
            assert backend.get_secret("MY_KEY") == "my_value"

    def test_get_secret_raises_key_error(self):
        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {}}}
        mock_hvac.Client.return_value = mock_client
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            backend = VaultSecretsBackend(url="https://vault:8200", token="test")
            with pytest.raises(KeyError, match="not found in Vault"):
                backend.get_secret("MISSING")


class TestGetSecretsBackend:
    """Tests for get_secrets_backend factory."""

    def test_default_returns_env_backend(self, monkeypatch):
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "env")
        backend = get_secrets_backend()
        assert isinstance(backend, EnvSecretsBackend)

    def test_vault_returns_vault_backend(self, monkeypatch):
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "vault")
        monkeypatch.setenv("VAULT_ADDR", "https://vault:8200")
        monkeypatch.setenv("VAULT_TOKEN", "test-token")
        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            backend = get_secrets_backend()
            assert isinstance(backend, VaultSecretsBackend)

    def test_vault_raises_without_config(self, monkeypatch):
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "vault")
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        with pytest.raises(ValueError, match="VAULT_ADDR and VAULT_TOKEN"):
            get_secrets_backend()

    def test_unknown_backend_raises(self, monkeypatch):
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "unknown")
        with pytest.raises(ValueError, match="Unknown SECRETS_BACKEND"):
            get_secrets_backend()
