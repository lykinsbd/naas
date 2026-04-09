"""Credential encryption for Redis at-rest protection.

See ADR 0006 for design rationale.
"""

import json
import logging
import os

from cryptography.fernet import Fernet, MultiFernet

from naas.library.auth import Credentials

logger = logging.getLogger(__name__)

_fernet: MultiFernet | None = None


def _get_fernet() -> MultiFernet:
    """Build or return cached MultiFernet.

    Tries the Flask secrets backend first (API process), falls back to
    the NAAS_ENCRYPTION_KEY env var directly (worker process).
    """
    global _fernet  # noqa: PLW0603
    if _fernet is not None:
        return _fernet
    raw: str | None = None
    try:
        from flask import current_app

        secrets = current_app.config["secrets"]
        raw = secrets.get_secret("NAAS_ENCRYPTION_KEY")
    except (RuntimeError, KeyError):
        # No Flask app context (worker) — read env var directly
        raw = os.environ.get("NAAS_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError("NAAS_ENCRYPTION_KEY not available")
    keys = [Fernet(k.strip()) for k in raw.split(",")]
    _fernet = MultiFernet(keys)
    return _fernet


def encrypt_credentials(creds: Credentials) -> bytes:
    """Encrypt a Credentials object for storage in Redis."""
    payload = json.dumps({"u": creds.username, "p": creds.password, "e": creds.enable}).encode()
    return _get_fernet().encrypt(payload)


def decrypt_credentials(token: bytes) -> Credentials:
    """Decrypt a Credentials object from Redis.

    Raises:
        cryptography.fernet.InvalidToken: If decryption fails (wrong key, corrupted data).
    """
    data = json.loads(_get_fernet().decrypt(token))
    return Credentials(username=data["u"], password=data["p"], enable=data["e"])
