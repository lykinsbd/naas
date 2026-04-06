"""API resources for API key management.

All endpoints require Basic auth — API keys cannot be used to manage other keys.
"""

from flask import request
from flask_restful import Resource

from naas import __base_response__
from naas.config import NAAS_ADMIN_SECRET
from naas.library.api_keys import create_api_key, list_api_keys, revoke_api_key
from naas.library.errorhandlers import NoAuth


def _require_admin_auth() -> None:
    """Ensure the request uses Basic auth with the admin secret."""
    if not NAAS_ADMIN_SECRET:
        raise NoAuth  # admin secret not configured — deny all key management
    auth = request.authorization
    if not auth or not auth.username or auth.password != NAAS_ADMIN_SECRET:
        raise NoAuth


class ApiKeys(Resource):
    """Resource for creating and listing API keys."""

    @staticmethod
    def post():
        """Create a new API key. Returns the JWT token once."""
        _require_admin_auth()
        data = request.get_json(force=True)
        result = create_api_key(
            role=data.get("role", "admin"),
            contexts=data.get("contexts"),
            ttl=data.get("ttl"),
            created_by=request.authorization.username,  # type: ignore[union-attr]
        )
        return {**result, **__base_response__}, 201

    @staticmethod
    def get():
        """List all active API keys (metadata only, not tokens)."""
        _require_admin_auth()
        return {"keys": list_api_keys(), **__base_response__}, 200


class ApiKey(Resource):
    """Resource for revoking a single API key."""

    @staticmethod
    def delete(key_id: str):
        """Revoke an API key."""
        _require_admin_auth()
        if revoke_api_key(key_id):
            return "", 204
        return {"error": f"Key '{key_id}' not found", **__base_response__}, 404
