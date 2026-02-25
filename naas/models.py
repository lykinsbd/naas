"""Pydantic models for request/response validation."""

from ipaddress import IPv4Address, IPv6Address
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SendCommandRequest(BaseModel):
    """Request model for send_command endpoint."""

    ip: IPv4Address | IPv6Address = Field(..., description="Device IP address")
    commands: list[str] = Field(..., min_length=1, description="Commands to execute")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type")
    delay_factor: int = Field(default=1, ge=1, description="Netmiko delay factor")
    enable: str | None = Field(default=None, description="Enable password")

    @field_validator("commands")
    @classmethod
    def commands_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure commands list contains non-empty strings."""
        if not all(cmd.strip() for cmd in v):
            raise ValueError("commands must contain non-empty strings")
        return v


class SendConfigRequest(BaseModel):
    """Request model for send_config endpoint."""

    ip: IPv4Address | IPv6Address = Field(..., description="Device IP address")
    config: list[str] | None = Field(default=None, min_length=1, description="Configuration commands")
    commands: list[str] | None = Field(default=None, min_length=1, description="Configuration commands (alias)")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type")
    delay_factor: int = Field(default=1, ge=1, description="Netmiko delay factor")
    enable: str | None = Field(default=None, description="Enable password")
    save_config: bool = Field(default=False, description="Save configuration after applying")
    commit: bool = Field(default=False, description="Commit configuration (Juniper)")

    @field_validator("config", "commands")
    @classmethod
    def config_not_empty(cls, v: list[str] | None) -> list[str] | None:
        """Ensure config list contains non-empty strings."""
        if v is not None and not all(cmd.strip() for cmd in v):
            raise ValueError("config/commands must contain non-empty strings")
        return v

    def model_post_init(self, __context) -> None:
        """Use commands as config if config not provided."""
        if self.config is None and self.commands is not None:
            object.__setattr__(self, "config", self.commands)
        elif self.config is None:
            raise ValueError("Either 'config' or 'commands' field is required")


class JobResponse(BaseModel):
    """Response model for job submission."""

    job_id: str = Field(..., description="Unique job identifier")
    message: str = Field(..., description="Status message")


class JobResultResponse(BaseModel):
    """Response model for job results."""

    job_id: str
    status: str
    result: Any | None = None
    error: str | None = None
