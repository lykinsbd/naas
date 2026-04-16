"""Unit tests for MCP resources."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from fastmcp.client import Client

from naas_client.models import ContextsResponse, FailedJobsResponse, HealthCheckResponse


async def test_health_resource(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.healthcheck.return_value = HealthCheckResponse.model_validate({
        "status": "healthy",
        "version": "2.1.0a1",
        "uptime_seconds": 3600,
        "components": {
            "redis": {"status": "healthy"},
            "workers": {"status": "healthy"},
            "queue": {"status": "healthy"},
        },
    })

    contents = await mcp_client.read_resource("naas://health")

    mock_naas_client.healthcheck.assert_called_once()
    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert data["status"] == "healthy"


async def test_contexts_resource(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.list_contexts.return_value = ContextsResponse.model_validate({
        "contexts": [{"name": "default", "queue_depth": 0, "workers": 2}],
    })

    contents = await mcp_client.read_resource("naas://contexts")

    mock_naas_client.list_contexts.assert_called_once()
    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert len(data["contexts"]) == 1
    assert data["contexts"][0]["name"] == "default"


async def test_failed_jobs_resource(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.failed_jobs.return_value = FailedJobsResponse.model_validate({
        "jobs": [{"job_id": "fail-1", "error": "Connection timed out", "failed_at": "2026-04-15T10:00:00Z"}],
        "total": 1,
    })

    contents = await mcp_client.read_resource("naas://jobs/failed")

    mock_naas_client.failed_jobs.assert_called_once()
    data = json.loads(contents[0].text)  # type: ignore[union-attr]
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "fail-1"
