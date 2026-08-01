"""Pydantic models for request/response validation."""

import logging
import re
from ipaddress import ip_address
from typing import Any, Literal
from urllib.parse import urlparse

from netmiko import platforms as netmiko_platforms
from pydantic import BaseModel, Field, field_validator, model_validator

import naas.config as _naas_config

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


def _validate_webhook_url(v: str | None) -> str | None:
    """Validate webhook_url is a valid HTTPS URL (HTTP allowed only when WEBHOOK_ALLOW_HTTP=true)."""
    if v is None:
        return v
    parsed = urlparse(v)
    if _naas_config.WEBHOOK_ALLOW_HTTP:
        # HTTP allowed only in test/dev environments (WEBHOOK_ALLOW_HTTP=true)
        # Branch not reachable in production; pragma suppresses coverage miss
        allowed_schemes: set[str] = {"https", "http"}  # pragma: no cover
        scheme_msg = "https or http"  # pragma: no cover
    else:
        allowed_schemes = {"https"}
        scheme_msg = "https"
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ValueError(f"webhook_url must be a valid {scheme_msg} URL")
    return v


class _BaseCommandRequest(BaseModel):
    """Base model for command request endpoints with common fields and validators."""

    model_config = {"strict": True}

    host: str | None = Field(default=None, description="Device IP address or hostname")
    ip: str | None = Field(default=None, description="Deprecated: use host instead (v1 compat)")
    commands: list[str] = Field(..., min_length=1, description="Commands to execute")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type (use 'autodetect' for SSHDetect)")
    device_type: str | None = Field(default=None, description="Deprecated: use platform instead (v1 compat)")
    read_timeout: float = Field(default=30.0, ge=1.0, description="Read timeout in seconds for device responses")
    conn_timeout: float = Field(default=10.0, ge=1.0, description="TCP connection timeout in seconds")
    context: str = Field(
        default="default",
        description="Routing context for multi-segment environments (e.g. 'corp', 'oob-dc1', 'hk-prod')",
    )
    tags: dict[str, str] | None = Field(
        default=None,
        description="Optional key-value metadata tags (max 10, keys/values max 64 chars, alphanumeric + hyphens/underscores/colons)",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Optional HTTPS URL to POST a job completion notification to (never includes results)",
    )
    webhook_secret: str | None = Field(
        default=None,
        description="Optional shared secret for HMAC-SHA256 webhook payload signing",
    )
    username: str | None = Field(default=None, description="Device username (required for API key auth)")
    password: str | None = Field(default=None, description="Device password (required for API key auth)")
    enable: str | None = Field(default=None, description="Enable password (optional, defaults to password)")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate tags via shared _validate_tags function."""
        return _validate_tags(v)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate webhook_url is a valid HTTPS URL."""
        return _validate_webhook_url(v)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str | None) -> str | None:
        """Validate host is a valid IP address or hostname."""
        if v is None:
            return v  # pragma: no cover
        try:
            ip_address(v)
            return v
        except Exception:
            pass
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

    @model_validator(mode="before")
    @classmethod
    def resolve_deprecated_fields(cls, data: Any) -> Any:
        """Map deprecated v1 fields: ip → host, device_type → platform."""
        if isinstance(data, dict):
            if "ip" in data and data["ip"] is not None:
                data.setdefault("host", data.pop("ip"))
            else:
                data.pop("ip", None)
            if "device_type" in data and data["device_type"] is not None:
                data["platform"] = data.pop("device_type")
            else:
                data.pop("device_type", None)
            if not data.get("host"):
                raise ValueError("host (or ip for v1) is required")
        return data


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

    host: str | None = Field(default=None, description="Device IP address or hostname")
    ip: str | None = Field(default=None, description="Deprecated: use host instead (v1 compat)")
    config: list[str] | None = Field(default=None, min_length=1, description="Configuration commands")
    commands: list[str] | None = Field(default=None, min_length=1, description="Configuration commands (alias)")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    platform: str = Field(default="cisco_ios", description="Netmiko device type (use 'autodetect' for SSHDetect)")
    device_type: str | None = Field(default=None, description="Deprecated: use platform instead (v1 compat)")
    read_timeout: float = Field(default=30.0, ge=1.0, description="Read timeout in seconds for device responses")
    conn_timeout: float = Field(default=10.0, ge=1.0, description="TCP connection timeout in seconds")
    save_config: bool = Field(default=False, description="Save configuration after applying")
    commit: bool = Field(default=False, description="Commit configuration (Juniper)")
    context: str = Field(default="default", description="Routing context for multi-segment environments")
    tags: dict[str, str] | None = Field(
        default=None,
        description="Optional key-value metadata tags (max 10, keys/values max 64 chars)",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Optional HTTPS URL to POST a job completion notification to (never includes results)",
    )
    webhook_secret: str | None = Field(
        default=None,
        description="Optional shared secret for HMAC-SHA256 webhook payload signing",
    )
    username: str | None = Field(default=None, description="Device username (required for API key auth)")
    password: str | None = Field(default=None, description="Device password (required for API key auth)")
    enable: str | None = Field(default=None, description="Enable password (optional, defaults to password)")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate tags via shared _validate_tags function."""
        return _validate_tags(v)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        """Validate webhook_url is a valid HTTPS URL."""
        return _validate_webhook_url(v)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str | None) -> str | None:
        """Validate host is a valid IP address or hostname."""
        if v is None:
            return v  # pragma: no cover
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

    @model_validator(mode="before")
    @classmethod
    def resolve_deprecated_fields(cls, data: Any) -> Any:
        """Map deprecated v1 fields: ip → host, device_type → platform."""
        if isinstance(data, dict):
            if "ip" in data and data["ip"] is not None:
                data.setdefault("host", data.pop("ip"))
            else:
                data.pop("ip", None)
            if "device_type" in data and data["device_type"] is not None:
                data["platform"] = data.pop("device_type")
            else:
                data.pop("device_type", None)
            if not data.get("host"):
                raise ValueError("host (or ip for v1) is required")
        return data

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
    error_code: str | None = None
    error_retryable: bool | None = None
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


# ---------------------------------------------------------------------------
# Response models for endpoints that previously returned raw dicts
# ---------------------------------------------------------------------------


class HealthComponentStatus(BaseModel):
    """Status of a single health component."""

    status: str = Field(..., description="Component status (healthy, unhealthy, no_workers)")


class QueueHealth(HealthComponentStatus):
    """Queue health with depth."""

    depth: int = Field(default=0, description="Number of jobs in queue")


class WorkersHealth(HealthComponentStatus):
    """Worker health with count and active jobs."""

    count: int = Field(default=0, description="Number of worker pods/hosts")
    active_jobs: int = Field(default=0, description="Jobs currently processing")


class HealthComponents(BaseModel):
    """Health check component statuses."""

    redis: HealthComponentStatus = Field(..., description="Redis connectivity")
    queue: QueueHealth = Field(..., description="Job queue status")
    workers: WorkersHealth = Field(..., description="Worker pool status")
    failed_jobs: int = Field(default=0, description="Number of failed jobs")


class HealthCheckResponse(BaseModel):
    """Response model for GET /healthcheck."""

    status: str = Field(..., description="Overall status: healthy, degraded, or no_workers")
    version: str = Field(..., description="NAAS version")
    uptime_seconds: int = Field(..., description="Seconds since API start")
    components: HealthComponents = Field(..., description="Component health details")


class JobSummary(BaseModel):
    """Summary of a single job in a list response."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    created_at: str | None = Field(default=None, description="ISO 8601 creation timestamp")
    ended_at: str | None = Field(default=None, description="ISO 8601 completion timestamp")
    tags: dict[str, str] | None = Field(default=None, description="Job metadata tags")


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Results per page")
    total: int = Field(..., description="Total number of results")
    pages: int = Field(..., description="Total number of pages")


class ListJobsResponse(BaseModel):
    """Response model for GET /v2/jobs."""

    jobs: list[JobSummary] = Field(..., description="List of jobs")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class FailedJobSummary(BaseModel):
    """Summary of a single failed job."""

    job_id: str = Field(..., description="Unique job identifier")
    host: str = Field(default="", description="Target device host")
    platform: str = Field(default="", description="Netmiko platform")
    port: int = Field(default=22, description="SSH port")
    failed_at: str | None = Field(default=None, description="ISO 8601 failure timestamp")
    error: str | None = Field(default=None, description="Sanitized error message")
    error_code: str | None = Field(default=None, description="Machine-parseable error code")
    error_retryable: bool | None = Field(default=None, description="Whether the caller can retry")
    func: str = Field(default="", description="Worker function name")


class FailedJobsResponse(BaseModel):
    """Response model for GET /v2/jobs/failed."""

    jobs: list[FailedJobSummary] = Field(..., description="List of failed jobs")
    total: int = Field(..., description="Total number of failed jobs")


class ApiKeyCreateResponse(BaseModel):
    """Response model for POST /v2/api-keys and POST /v2/api-keys/{id}/rotate."""

    key_id: str = Field(..., description="Key identifier")
    token: str = Field(..., description="JWT token (shown once)")
    role: str = Field(..., description="Assigned role")
    contexts: list[str] = Field(default_factory=list, description="Allowed contexts")
    expires_at: str = Field(..., description="ISO 8601 expiration timestamp")


class ApiKeyListItem(BaseModel):
    """API key metadata (no token)."""

    key_id: str = Field(..., description="Key identifier")
    role: str = Field(..., description="Assigned role")
    contexts: list[str] = Field(default_factory=list, description="Allowed contexts")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    expires_at: str = Field(..., description="ISO 8601 expiration timestamp")
    created_by: str = Field(..., description="Creator identity")


class ApiKeyListResponse(BaseModel):
    """Response model for GET /v2/api-keys."""

    keys: list[ApiKeyListItem] = Field(..., description="Active API keys")


# --- Batch / Bulk Operations Models ---


class BatchDeviceEntry(BaseModel):
    """A single device in a batch request.

    At minimum requires host and platform. Optional fields override
    the batch-level defaults for credentials and port.
    """

    model_config = {"strict": True}

    host: str = Field(..., description="Device IP address or hostname")
    platform: str = Field(..., description="Netmiko device type")
    port: int | None = Field(default=None, ge=1, le=65535, description="SSH port override")
    username: str | None = Field(default=None, description="Device username override")
    password: str | None = Field(default=None, description="Device password override")
    enable: str | None = Field(default=None, description="Enable password override")
    context: str | None = Field(default=None, description="Routing context override for this device")

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

    @field_validator("platform")
    @classmethod
    def platform_is_valid(cls, v: str) -> str:
        """Ensure platform is a valid Netmiko device type."""
        if v not in netmiko_platforms:
            raise ValueError(f"Invalid platform '{v}'. Must be a valid Netmiko device type.")
        return v


class BatchSendCommandRequest(BaseModel):
    """Request model for POST /v2/send-command/batch.

    Submits the same commands to multiple devices. Each device can override
    credentials and routing context. Returns a batch ID for tracking.
    """

    model_config = {"strict": True}

    devices: list[BatchDeviceEntry] = Field(..., min_length=1, description="List of target devices")
    commands: list[str] = Field(..., min_length=1, description="Commands to execute on each device")
    username: str | None = Field(default=None, description="Default username for all devices")
    password: str | None = Field(default=None, description="Default password for all devices")
    enable: str | None = Field(default=None, description="Default enable password for all devices")
    port: int = Field(default=22, ge=1, le=65535, description="Default SSH port for all devices")
    context: str = Field(default="default", description="Default routing context for all devices")
    expect_string: str | None = Field(
        default=None, description="Regex pattern to match in device output (applied to all devices)"
    )
    tags: dict[str, str] | None = Field(default=None, description="Metadata tags applied to all jobs in the batch")

    @field_validator("commands")
    @classmethod
    def commands_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure commands list contains non-empty strings."""
        if not all(cmd.strip() for cmd in v):
            raise ValueError("commands must contain non-empty strings")
        return v


class BatchSendConfigRequest(BaseModel):
    """Request model for POST /v2/send-config/batch.

    Pushes the same configuration commands to multiple devices. Each device
    can override credentials and routing context. commit/save_config apply
    uniformly to all devices.
    """

    model_config = {"strict": True}

    devices: list[BatchDeviceEntry] = Field(..., min_length=1, description="List of target devices")
    commands: list[str] = Field(..., min_length=1, description="Configuration commands to apply on each device")
    username: str | None = Field(default=None, description="Default username for all devices")
    password: str | None = Field(default=None, description="Default password for all devices")
    enable: str | None = Field(default=None, description="Default enable password for all devices")
    port: int = Field(default=22, ge=1, le=65535, description="Default SSH port for all devices")
    context: str = Field(default="default", description="Default routing context for all devices")
    commit: bool = Field(default=False, description="Commit configuration on platforms that support it")
    save_config: bool = Field(default=False, description="Save running config to startup after applying")
    tags: dict[str, str] | None = Field(default=None, description="Metadata tags applied to all jobs in the batch")

    @field_validator("commands")
    @classmethod
    def commands_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure commands list contains non-empty strings."""
        if not all(cmd.strip() for cmd in v):
            raise ValueError("commands must contain non-empty strings")
        return v


class BatchSubmitResponse(BaseModel):
    """Response for successful batch submission (202 Accepted)."""

    batch_id: str = Field(..., description="Unique batch identifier")
    job_ids: list[str] = Field(..., description="Individual job IDs created for each device")
    total: int = Field(..., description="Number of jobs created")


class BatchJobStatus(BaseModel):
    """Status of a single job within a batch."""

    job_id: str = Field(..., description="Unique job identifier")
    host: str = Field(..., description="Target device host")
    status: str = Field(..., description="Job status (queued, started, finished, failed)")


class BatchStatusResponse(BaseModel):
    """Response for GET /v2/batches/{batch_id}."""

    batch_id: str = Field(..., description="Unique batch identifier")
    total: int = Field(..., description="Total number of jobs in batch")
    completed: int = Field(..., description="Number of finished jobs")
    pending: int = Field(..., description="Number of queued or started jobs")
    failed: int = Field(..., description="Number of failed jobs")
    jobs: list[BatchJobStatus] = Field(..., description="Per-job status breakdown")
