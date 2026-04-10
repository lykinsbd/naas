"""Public models for naas-client.

Re-exports generated models from the OpenAPI spec with ergonomic aliases,
plus custom types not present in the spec.
"""

from __future__ import annotations

from enum import StrEnum

from naas_client._generated import (
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    ContextInfo,
    ContextsResponse,
    FailedJobsResponse,
    FailedJobSummary,
    HealthCheckResponse,
    HealthComponentStatus,
    JobSummary,
    ListJobsResponse,
    PaginationInfo,
    QueueHealth,
    SendCommandRequest,
    SendCommandStructuredRequest,
    SendConfigRequest,
    WorkersHealth,
)
from naas_client._generated import (
    JobResponse as JobSubmission,
)
from naas_client._generated import (
    JobResultResponse as JobResult,
)


class JobStatus(StrEnum):
    """Job lifecycle states."""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"


__all__ = [
    "ApiKeyCreateResponse",
    "ApiKeyListItem",
    "ApiKeyListResponse",
    "ContextInfo",
    "ContextsResponse",
    "FailedJobSummary",
    "FailedJobsResponse",
    "HealthCheckResponse",
    "HealthComponentStatus",
    "JobResult",
    "JobStatus",
    "JobSubmission",
    "JobSummary",
    "ListJobsResponse",
    "PaginationInfo",
    "QueueHealth",
    "SendCommandRequest",
    "SendCommandStructuredRequest",
    "SendConfigRequest",
    "WorkersHealth",
]
