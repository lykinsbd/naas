"""Integration tests for secrets backends."""

import pytest
import requests

from naas.library.secrets import AWSSecretsBackend, EnvSecretsBackend, VaultSecretsBackend, get_secrets_backend

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


LOCALSTACK_URL = "http://localhost:14566"
AWS_SECRET_NAME = "naas-integration-test"
AWS_REGION = "us-east-1"


@pytest.fixture(scope="module")
def aws_seed():
    """Seed LocalStack Secrets Manager with test secrets."""
    import boto3

    client = boto3.client(
        "secretsmanager",
        endpoint_url=LOCALSTACK_URL,
        region_name=AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    import json

    client.create_secret(
        Name=AWS_SECRET_NAME,
        SecretString=json.dumps({"DB_PASSWORD": "test-db-pass", "API_TOKEN": "test-api-token"}),
    )
    yield


@pytest.fixture()
def wait_for_localstack():
    """Wait for LocalStack to be ready."""
    import time

    for _ in range(10):
        try:
            r = requests.get(f"{LOCALSTACK_URL}/_localstack/health", timeout=2)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            time.sleep(1)
    pytest.fail("LocalStack did not become ready")


class TestAWSSecretsBackendIntegration:
    """Integration tests for AWSSecretsBackend against LocalStack."""

    def test_read_seeded_secret(self, wait_for_localstack, aws_seed, monkeypatch):
        """Read secrets seeded into LocalStack."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        backend = AWSSecretsBackend(secret_name=AWS_SECRET_NAME, region=AWS_REGION, endpoint_url=LOCALSTACK_URL)
        assert backend.get_secret("DB_PASSWORD") == "test-db-pass"
        assert backend.get_secret("API_TOKEN") == "test-api-token"

    def test_missing_key_raises(self, wait_for_localstack, aws_seed, monkeypatch):
        """Missing key raises KeyError."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        backend = AWSSecretsBackend(secret_name=AWS_SECRET_NAME, region=AWS_REGION, endpoint_url=LOCALSTACK_URL)
        with pytest.raises(KeyError, match="not found in AWS secret"):
            backend.get_secret("NONEXISTENT")

    def test_factory_creates_aws_backend(self, wait_for_localstack, aws_seed, monkeypatch):
        """Factory creates AWSSecretsBackend when configured."""
        monkeypatch.setattr("naas.library.secrets.SECRETS_BACKEND", "aws")
        monkeypatch.setenv("AWS_SECRET_NAME", AWS_SECRET_NAME)
        monkeypatch.setenv("AWS_REGION", AWS_REGION)
        monkeypatch.setenv("AWS_ENDPOINT_URL", LOCALSTACK_URL)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        backend = get_secrets_backend()
        assert isinstance(backend, AWSSecretsBackend)
