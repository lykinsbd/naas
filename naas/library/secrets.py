"""Pluggable secrets backend for application secret retrieval.

Provides a Protocol and implementations for loading secrets from
environment variables (default) or HashiCorp Vault.

See ADR 0002 for design rationale.
"""

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)

SECRETS_BACKEND: str = os.environ.get("SECRETS_BACKEND", "env")


class SecretsBackend(Protocol):
    """Interface for secret retrieval backends."""

    def get_secret(self, name: str) -> str:
        """Retrieve a secret by name.

        Args:
            name: Secret identifier.

        Returns:
            The secret value.

        Raises:
            KeyError: If the secret is not found.
        """
        ...


class EnvSecretsBackend:
    """Read secrets from environment variables."""

    def get_secret(self, name: str) -> str:
        """Retrieve a secret from environment variables.

        Args:
            name: Environment variable name.

        Returns:
            The environment variable value.

        Raises:
            KeyError: If the environment variable is not set.
        """
        try:
            return os.environ[name]
        except KeyError:
            raise KeyError(f"Secret '{name}' not found in environment variables") from None


class VaultSecretsBackend:
    """Read secrets from HashiCorp Vault KV v2 engine.

    Requires the ``hvac`` package: ``pip install naas[vault]``
    """

    def __init__(self, url: str, token: str, path: str = "secret/data/naas") -> None:
        """Initialize Vault client.

        Args:
            url: Vault server URL.
            token: Vault authentication token.
            path: KV v2 mount path and secret path.
        """
        try:
            import hvac
        except ImportError:
            raise ImportError("VaultSecretsBackend requires 'hvac'. Install with: pip install naas[vault]") from None

        self._client = hvac.Client(url=url, token=token)
        self._path = path
        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def get_secret(self, name: str) -> str:
        """Retrieve a secret from Vault.

        Args:
            name: Key within the Vault secret.

        Returns:
            The secret value.

        Raises:
            KeyError: If the key is not found in Vault.
        """
        response = self._client.secrets.kv.v2.read_secret_version(path=self._path)
        data: dict[str, str] = response["data"]["data"]
        if name not in data:
            raise KeyError(f"Secret '{name}' not found in Vault path '{self._path}'")
        return data[name]


def get_secrets_backend() -> SecretsBackend:
    """Create a secrets backend based on SECRETS_BACKEND config.

    Returns:
        A SecretsBackend implementation.

    Raises:
        ValueError: If SECRETS_BACKEND is not a recognized value.
    """
    backend = SECRETS_BACKEND.lower()

    if backend == "env":
        logger.info("Using environment variable secrets backend")
        return EnvSecretsBackend()

    if backend == "vault":
        url = os.environ.get("VAULT_ADDR", "")
        token = os.environ.get("VAULT_TOKEN", "")
        path = os.environ.get("VAULT_SECRETS_PATH", "secret/data/naas")
        if not url or not token:
            raise ValueError("VaultSecretsBackend requires VAULT_ADDR and VAULT_TOKEN environment variables")
        logger.info("Using HashiCorp Vault secrets backend at %s", url)
        return VaultSecretsBackend(url=url, token=token, path=path)

    raise ValueError(f"Unknown SECRETS_BACKEND: '{backend}'. Valid options: env, vault")
