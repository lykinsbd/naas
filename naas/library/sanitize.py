"""
sanitize.py
Credential sanitization for API responses.
Strips credential values from strings to prevent accidental exposure.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from naas.library.auth import Credentials

_REDACTED = "<redacted>"


def sanitize_error(error: str | None, credentials: "Credentials | None" = None) -> str | None:
    """
    Remove credential values from an error string.

    Args:
        error: The error string to sanitize (may be None)
        credentials: Optional Credentials whose values to redact

    Returns:
        Sanitized error string, or None if input was None
    """
    if error is None:
        return None

    result = error

    if credentials:
        for value in (credentials.password, credentials.enable, credentials.username):
            if value:
                result = result.replace(value, _REDACTED)

    return result
