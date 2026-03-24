"""Pydantic models for request/response validation."""

import logging
import re
from ipaddress import ip_address
from typing import Any, Literal

from netmiko import platforms as netmiko_platforms
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_TAGS_KEY_RE = re.compile(r"^[a-zA-Z0-9_\-:]{1,64}$")
_HOSTNAME_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*" r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
)


def _validate_tags(v: dict[str, str] | None) -> dict[str, str] | None:
    """Validate tags: max 10 entries, keys/values max 64 chars, alphanumeric + hyphens/underscores/colons."""
    if v is None:
        return v
    if len(v) > 10:
        raise ValueError("tags must contain at most 10 entries")
    for k, val in v.items():
        if not _TAGS_KEY_RE.match(k):
            raise ValueError(f"tag key '{k}' must be alphanumeric with hyphens, underscores, or colons (max 64 chars)")
        if not _TAGS_KEY_RE.match(val):
            raise ValueError(
                f"tag value '{val}' must be alphanumeric with hyphens, underscores, or colons (max 64 chars)"
            )
    return v


def _handle_device_type(data: dict[str, Any]) -> dict[str, Any]:
    """
    Map deprecated device_type parameter to platform with warning.

    Args:
        data: Request data dictionary that may contain device_type

    Returns:
        Modified data dictionary with device_type mapped to platform
    """
    data = data.copy()  # Avoid mutating caller's dict
    if "device_type" in data:
        logger.warning(
            "Parameter 'device_type' is deprecated, use 'platform' instead. "
            "Support for 'device_type' will be removed in v2.0"
        )
        if "platform" not in data:
            data["platform"] = data.pop("device_type")
        else:
            data.pop("device_type")
    return data


def _handle_ip(data: dict[str, Any]) -> dict[str, Any]:
    """
    Map deprecated ip parameter to host with warning.

    Args:
        data: Request data dictionary that may contain ip

    Returns:
        Modified data dictionary with ip mapped to host
    """
    data = data.copy()
    if "ip" in data:
        logger.warning("Parameter 'ip' is deprecated, use 'host' instead. Support for 'ip' will be removed in v2.0")
        if "host" not in data:
            data["host"] = data.pop("ip")
        else:
            data.pop("ip")
    return data


class _BaseCommandRequest(BaseModel):
    """Base model for command request endpoints with common fields and validators."""

    model_config = {"strict": True}

    host: str = Field(..., description="Device IP address or hostname")
    commands: list[str] = Field(..., min_length=1, description="Commands to execute")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type (use 'autodetect' for SSHDetect)")
    read_timeout: float = Field(default=30.0, ge=1.0, description="Read timeout in seconds for device responses")
    context: str = Field(
        default="default",
        description="Routing context for multi-segment environments (e.g. 'corp', 'oob-dc1', 'hk-prod')",
    )
    tags: dict[str, str] | None = Field(
        default=None,
        description="Optional key-value metadata tags (max 10, keys/values max 64 chars, alphanumeric + hyphens/underscores/colons)",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate tags via shared _validate_tags function."""
        return _validate_tags(v)

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_params(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Support deprecated device_type and ip parameters."""
        data = _handle_device_type(data)
        return _handle_ip(data)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is a valid IP address or hostname."""
        # Try IP first
        try:
            ip_address(v)
            return v
        except Exception:
            pass
        # Try hostname
        if len(v) <= 253 and _HOSTNAME_RE.match(v):
            return v
        raise ValueError(f"'{v}' is not a valid IP address or hostname")

    @field_validator("commands")
    @classmethod
    def commands_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure commands list contains non-empty strings."""
        if not all(cmd.strip() for cmd in v):
            raise ValueError("commands must contain non-empty strings")
        return v

    @field_validator("platform")
    @classmethod
    def platform_is_valid(cls, v: str) -> str:
        """Ensure platform is a valid Netmiko device type."""
        if v not in netmiko_platforms:
            raise ValueError(f"Invalid platform '{v}'. Must be a valid Netmiko device type.")
        return v


class SendCommandRequest(_BaseCommandRequest):
    """Request model for send_command endpoint.

    Uses strict=True because spectree passes Flask's parsed JSON body (native Python
    types) to model_validate(). Strict mode rejects type mismatches (e.g. port sent
    as a JSON string instead of a number) rather than silently coercing them.

    NOTE: Do NOT use strict=True on query parameter models (e.g. ListJobsQuery).
    Query params always arrive as strings from werkzeug; strict mode would reject
    valid integer params like ?page=2 because '2' is a str, not an int.
    """

    expect_string: str | None = Field(
        default=None, description="Regex pattern to match in device output (overrides prompt detection)"
    )


class SendCommandStructuredRequest(_BaseCommandRequest):
    """Request model for structured send_command with TextFSM or TTP parsing.

    Returns parsed output as list[dict] per command. Falls back to raw string
    if no template is found.
    """

    textfsm_template: str | None = Field(
        default=None, description="Custom TextFSM template (uses ntc-templates if not provided)"
    )
    ttp_template: str | None = Field(
        default=None,
        description="TTP template string or ttp://<path> reference (mutually exclusive with textfsm_template)",
    )

    @model_validator(mode="after")
    def validate_parser_exclusivity(self) -> "SendCommandStructuredRequest":
        """Ensure textfsm_template and ttp_template are mutually exclusive."""
        if self.textfsm_template is not None and self.ttp_template is not None:
            raise ValueError("textfsm_template and ttp_template are mutually exclusive")
        return self


class SendConfigRequest(BaseModel):
    """Request model for send_config endpoint.

    Uses strict=True for the same reason as SendCommandRequest — see that class
    for the strict vs. non-strict rationale.
    """

    model_config = {"strict": True}

    host: str = Field(..., description="Device IP address or hostname")
    config: list[str] | None = Field(default=None, min_length=1, description="Configuration commands")
    commands: list[str] | None = Field(default=None, min_length=1, description="Configuration commands (alias)")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type (use 'autodetect' for SSHDetect)")
    read_timeout: float = Field(default=30.0, ge=1.0, description="Read timeout in seconds for device responses")
    save_config: bool = Field(default=False, description="Save configuration after applying")
    commit: bool = Field(default=False, description="Commit configuration (Juniper)")
    context: str = Field(default="default", description="Routing context for multi-segment environments")
    tags: dict[str, str] | None = Field(
        default=None,
        description="Optional key-value metadata tags (max 10, keys/values max 64 chars)",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate tags via shared _validate_tags function."""
        return _validate_tags(v)

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_params(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Support deprecated device_type and ip parameters."""
        data = _handle_device_type(data)
        return _handle_ip(data)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is a valid IP address or hostname."""
        try:
            ip_address(v)
            return v
        except Exception:
            pass
        if len(v) <= 253 and _HOSTNAME_RE.match(v):
            return v
        raise ValueError(f"'{v}' is not a valid IP address or hostname")

    @field_validator("config", "commands")
    @classmethod
    def config_not_empty(cls, v: list[str] | None) -> list[str] | None:
        """Ensure config list contains non-empty strings."""
        if v is not None and not all(cmd.strip() for cmd in v):
            raise ValueError("config/commands must contain non-empty strings")
        return v

    @field_validator("platform")
    @classmethod
    def platform_is_valid(cls, v: str) -> str:
        """Ensure platform is a valid Netmiko device type."""
        if v not in netmiko_platforms:
            raise ValueError(f"Invalid platform '{v}'. Must be a valid Netmiko device type.")
        return v

    @model_validator(mode="after")
    def resolve_config(self) -> "SendConfigRequest":
        """Use commands as config if config not provided."""
        if self.config is None and self.commands is not None:
            self.config = self.commands
        elif self.config is None:
            raise ValueError("Either 'config' or 'commands' field is required")
        return self


class JobResponse(BaseModel):
    """Response model for job submission."""

    job_id: str = Field(..., description="Unique job identifier")
    message: str = Field(..., description="Status message")
    queue_position: int = Field(..., description="Approximate position in queue (1 = next to run)")
    enqueued_at: str = Field(..., description="ISO 8601 timestamp when job was enqueued")
    timeout: int = Field(..., description="Job timeout in seconds")
    idempotent: bool = Field(default=False, description="True if this response reuses an existing job")
    deduplicated: bool = Field(default=False, description="True if this response reuses an in-flight duplicate job")


class JobResultResponse(BaseModel):
    """Response model for job results."""

    job_id: str
    status: str
    results: Any | None = None
    error: str | None = None
    detected_platform: str | None = None
    tags: dict[str, str] | None = None


class ListJobsQuery(BaseModel):
    """Query parameters for the list jobs endpoint.

    NOTE: No strict=True here — query params arrive as strings from werkzeug.
    Pydantic's default lax mode coerces '2' -> 2 for int fields, which is required
    for query parameter models. See SendCommandRequest for the full rationale.
    """

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    status: Literal["finished", "failed", "started", "queued"] | None = None
    tag: str | None = Field(default=None, description="Filter by tag in 'key:value' format")


class ContextInfo(BaseModel):
    """Status of a single routing context."""

    name: str = Field(..., description="Context name")
    workers: int = Field(..., description="Number of active workers serving this context")
    queue_depth: int = Field(..., description="Number of jobs currently queued")


class ContextsResponse(BaseModel):
    """Response model for GET /v1/contexts."""

    contexts: list[ContextInfo] = Field(..., description="Active contexts")
