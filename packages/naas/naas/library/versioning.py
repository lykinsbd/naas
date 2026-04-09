"""API version detection helpers."""

from flask import request


def is_v2_request() -> bool:
    """Return True if the current request targets a /v2/ route."""
    return bool(request.path.startswith("/v2/"))
