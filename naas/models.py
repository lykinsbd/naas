"""Pydantic models for request/response validation."""

import logging
from typing import Any, Literal

from netmiko import platforms as netmiko_platforms
from pydantic import BaseModel, Field, IPvAnyAddress, field_validator, model_validator

logger = logging.getLogger(__name__)


def _handle_device_type(data: dict[str, Any]) -> dict[str, Any]:
    """Map deprecated device_type to platform with warning."""
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


class SendCommandRequest(BaseModel):
    """Request model for send_command endpoint.

    Uses strict=True because spectree passes Flask's parsed JSON body (native Python
    types) to model_validate(). Strict mode rejects type mismatches (e.g. port sent
    as a JSON string instead of a number) rather than silently coercing them.

    NOTE: Do NOT use strict=True on query parameter models (e.g. ListJobsQuery).
    Query params always arrive as strings from werkzeug; strict mode would reject
    valid integer params like ?page=2 because '2' is a str, not an int.
    """

    model_config = {"strict": True}

    ip: IPvAnyAddress = Field(..., description="Device IP address")
    commands: list[str] = Field(..., min_length=1, description="Commands to execute")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type")
    delay_factor: int = Field(default=1, ge=1, description="Netmiko delay factor")

    @model_validator(mode="before")
    @classmethod
    def handle_device_type(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Support deprecated device_type parameter."""
        return _handle_device_type(data)

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


class SendConfigRequest(BaseModel):
    """Request model for send_config endpoint.

    Uses strict=True for the same reason as SendCommandRequest — see that class
    for the strict vs. non-strict rationale.
    """

    model_config = {"strict": True}

    ip: IPvAnyAddress = Field(..., description="Device IP address")
    config: list[str] | None = Field(default=None, min_length=1, description="Configuration commands")
    commands: list[str] | None = Field(default=None, min_length=1, description="Configuration commands (alias)")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type")
    delay_factor: int = Field(default=1, ge=1, description="Netmiko delay factor")
    save_config: bool = Field(default=False, description="Save configuration after applying")
    commit: bool = Field(default=False, description="Commit configuration (Juniper)")

    @model_validator(mode="before")
    @classmethod
    def handle_device_type(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Support deprecated device_type parameter."""
        return _handle_device_type(data)

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


class JobResultResponse(BaseModel):
    """Response model for job results."""

    job_id: str
    status: str
    results: Any | None = None
    error: str | None = None


class ListJobsQuery(BaseModel):
    """Query parameters for the list jobs endpoint.

    NOTE: No strict=True here — query params arrive as strings from werkzeug.
    Pydantic's default lax mode coerces '2' -> 2 for int fields, which is required
    for query parameter models. See SendCommandRequest for the full rationale.
    """

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    status: Literal["finished", "failed", "started", "queued"] | None = None
