"""Integration tests for secrets backends."""

import pytest
import requests

from naas.library.secrets import EnvSecretsBackend, VaultSecretsBackend, get_secrets_backend

VAULT_ADDR = "http://localhost:18200"
VAULT_TOKEN = "test-root-token"
VAULT_SECRETS_PATH = "naas-test"


@pytest.fixture(scope="module")
def vault_seed():
    """Seed Vault with test secrets via HTTP API."""
    response = requests.post(
        f"{VAULT_ADDR}/v1/secret/data/{VAULT_SECRETS_PATH}",
        headers={"X-Vault-Token": VAULT_TOKEN},
        json={"data": {"ENCRYPTION_KEY": "test-enc-key", "HMAC_KEY": "test-hmac-key"}},
        timeout=5,
    )
    response.raise_for_status()
    yield


@pytest.fixture()
def wait_for_vault():
    """Wait for Vault to be ready."""
    for _ in range(10):
        try:
            r = requests.get(f"{VAULT_ADDR}/v1/sys/health", timeout=2)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            import time

            time.sleep(1)
    pytest.fail("Vault did not become ready")


class TestEnvSecretsBackendIntegration:
    """Integration tests for EnvSecretsBackend."""

    def test_round_trip(self, monkeypatch):
        """Set an env var and retrieve it through the backend."""
        monkeypatch.setenv("NAAS_TEST_SECRET", "integration-value")
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "env")
        backend = get_secrets_backend()
        assert isinstance(backend, EnvSecretsBackend)
        assert backend.get_secret("NAAS_TEST_SECRET") == "integration-value"

    def test_missing_secret_raises(self, monkeypatch):
        """Missing env var raises KeyError."""
        monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
        backend = EnvSecretsBackend()
        with pytest.raises(KeyError):
            backend.get_secret("DOES_NOT_EXIST")


class TestVaultSecretsBackendIntegration:
    """Integration tests for VaultSecretsBackend against real Vault dev server."""

    def test_read_seeded_secret(self, wait_for_vault, vault_seed):
        """Read a secret that was seeded into Vault."""
        backend = VaultSecretsBackend(url=VAULT_ADDR, token=VAULT_TOKEN, path=VAULT_SECRETS_PATH)
        assert backend.get_secret("ENCRYPTION_KEY") == "test-enc-key"
        assert backend.get_secret("HMAC_KEY") == "test-hmac-key"

    def test_missing_key_raises(self, wait_for_vault, vault_seed):
        """Missing key in Vault raises KeyError."""
        backend = VaultSecretsBackend(url=VAULT_ADDR, token=VAULT_TOKEN, path=VAULT_SECRETS_PATH)
        with pytest.raises(KeyError, match="not found in Vault"):
            backend.get_secret("NONEXISTENT_KEY")

    def test_factory_creates_vault_backend(self, wait_for_vault, vault_seed, monkeypatch):
        """Factory creates VaultSecretsBackend when configured."""
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "vault")
        monkeypatch.setenv("VAULT_ADDR", VAULT_ADDR)
        monkeypatch.setenv("VAULT_TOKEN", VAULT_TOKEN)
        monkeypatch.setenv("VAULT_SECRETS_PATH", VAULT_SECRETS_PATH)
        backend = get_secrets_backend()
        assert isinstance(backend, VaultSecretsBackend)
        assert backend.get_secret("ENCRYPTION_KEY") == "test-enc-key"

    def test_bad_token_raises(self, wait_for_vault):
        """Invalid token raises RuntimeError."""
        with pytest.raises(RuntimeError, match="authentication failed"):
            VaultSecretsBackend(url=VAULT_ADDR, token="bad-token", path=VAULT_SECRETS_PATH)
