"""JWT-based API key management.

Create, validate, and revoke API keys implemented as signed JWTs.
See ADR 0003 for design rationale.
"""

import json
import logging
import time
from uuid import uuid4

import jwt
from flask import current_app
from redis import Redis

from naas.config import API_KEY_DEFAULT_TTL, API_KEY_MAX_TTL
from naas.library.audit import emit_audit_event

logger = logging.getLogger(__name__)

REVOKED_KEYS_SET = "naas:revoked_keys"
KEY_META_PREFIX = "naas:api_keys:"


def _get_jwt_secret() -> str:
    """Load JWT signing secret from the secrets backend."""
    secrets = current_app.config["secrets"]
    result: str = secrets.get_secret("NAAS_JWT_SECRET")
    return result


def create_api_key(
    role: str = "admin",
    contexts: list[str] | None = None,
    ttl: int | None = None,
    created_by: str = "system",
) -> dict[str, str | list[str]]:
    """Create a new API key (JWT).

    Args:
        role: Role for this key (admin, operator, viewer).
        contexts: Allowed routing contexts. Defaults to ["*"] (all).
        ttl: Time-to-live in seconds. None uses API_KEY_DEFAULT_TTL, 0 for no expiry.
        created_by: Identity of the creator (for audit metadata).

    Returns:
        Dict with key_id, token, role, contexts, and expires_at.
    """
    if contexts is None:
        contexts = ["*"]
    if ttl is None:
        ttl = API_KEY_DEFAULT_TTL
    if API_KEY_MAX_TTL > 0 and ttl > API_KEY_MAX_TTL:
        ttl = API_KEY_MAX_TTL

    key_id = f"k-{uuid4().hex[:12]}"
    now = int(time.time())
    claims: dict = {
        "sub": key_id,
        "role": role,
        "contexts": contexts,
        "iat": now,
    }
    expires_at = ""
    if ttl > 0:
        claims["exp"] = now + ttl
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + ttl))

    token = jwt.encode(claims, _get_jwt_secret(), algorithm="HS256")

    # Store metadata in Redis for the list endpoint
    redis: Redis = current_app.config["redis"]
    meta = {
        "role": role,
        "contexts": json.dumps(contexts),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "expires_at": expires_at,
        "created_by": created_by,
    }
    redis.hset(f"{KEY_META_PREFIX}{key_id}", mapping=meta)  # type: ignore[arg-type]
    if ttl > 0:
        redis.expire(f"{KEY_META_PREFIX}{key_id}", ttl)

    emit_audit_event("apikey.created", key_id=key_id, role=role, contexts=",".join(contexts), created_by=created_by)

    return {
        "key_id": key_id,
        "token": token,
        "role": role,
        "contexts": contexts,
        "expires_at": expires_at,
    }


def validate_api_key(token: str) -> dict:
    """Validate a JWT API key and return its claims.

    Args:
        token: The JWT token string.

    Returns:
        Decoded claims dict with sub, role, contexts, iat, and optionally exp.

    Raises:
        jwt.InvalidTokenError: If the token is invalid, expired, or revoked.
    """
    claims: dict = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])

    # Check revocation
    redis: Redis = current_app.config["redis"]
    if redis.sismember(REVOKED_KEYS_SET, claims["sub"]):
        raise jwt.InvalidTokenError(f"API key '{claims['sub']}' has been revoked")

    return claims


def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key by adding it to the revocation set.

    Args:
        key_id: The key ID (sub claim) to revoke.

    Returns:
        True if the key was found and revoked, False if not found.
    """
    redis: Redis = current_app.config["redis"]

    # Check key exists in metadata
    if not redis.exists(f"{KEY_META_PREFIX}{key_id}"):
        return False

    # Add to revocation set
    redis.sadd(REVOKED_KEYS_SET, key_id)

    # Clean up metadata
    redis.delete(f"{KEY_META_PREFIX}{key_id}")

    logger.info("Revoked API key %s", key_id)
    emit_audit_event("apikey.revoked", key_id=key_id, revoked_by="admin")
    return True


def list_api_keys() -> list[dict[str, str]]:
    """List all active API key metadata (not tokens).

    Returns:
        List of dicts with key_id, role, contexts, created_at, expires_at, created_by.
    """
    redis: Redis = current_app.config["redis"]
    keys: list[bytes] = redis.keys(f"{KEY_META_PREFIX}*")  # type: ignore[assignment]
    result = []
    for key in keys:
        key_id = key.decode().removeprefix(KEY_META_PREFIX)
        meta: dict[bytes, bytes] = redis.hgetall(key.decode())  # type: ignore[assignment]
        if meta:
            result.append(
                {
                    "key_id": key_id,
                    "role": meta[b"role"].decode(),
                    "contexts": json.loads(meta[b"contexts"].decode()),
                    "created_at": meta[b"created_at"].decode(),
                    "expires_at": meta[b"expires_at"].decode(),
                    "created_by": meta[b"created_by"].decode(),
                }
            )
    return result


def rotate_api_key(key_id: str) -> dict[str, str | list[str]] | None:
    """Rotate an API key: create a new key with the same role/contexts, revoke the old one.

    Args:
        key_id: The key ID to rotate.

    Returns:
        New key dict (same as create_api_key), or None if key_id not found.
    """
    redis: Redis = current_app.config["redis"]
    meta: dict[bytes, bytes] = redis.hgetall(f"{KEY_META_PREFIX}{key_id}")  # type: ignore[assignment]
    if not meta:
        return None

    role = meta[b"role"].decode()
    contexts = json.loads(meta[b"contexts"].decode())
    created_by = meta[b"created_by"].decode()

    new_key = create_api_key(role=role, contexts=contexts, created_by=created_by)
    revoke_api_key(key_id)

    emit_audit_event("apikey.rotated", old_key_id=key_id, new_key_id=str(new_key["key_id"]), rotated_by=created_by)

    return new_key
