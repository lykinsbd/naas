"""Unit tests for MCP tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from naas_client.exceptions import NaasApiError, NaasConnectionError, NaasTimeoutError
from naas_client.models import JobResult, ListJobsResponse

if TYPE_CHECKING:
    from fastmcp.client import Client


def _mock_job(result: JobResult) -> AsyncMock:
    """Create a mock AsyncJob whose wait() returns the given result."""
    job = AsyncMock()
    job.job_id = result.job_id
    job.wait = AsyncMock(return_value=result)
    return job


def _finished_result(**overrides) -> JobResult:
    defaults = {"job_id": "test-123", "status": "finished", "results": {"show version": "Cisco IOS 15.1"}}
    defaults.update(overrides)
    return JobResult.model_validate(defaults)


# -- send_command --


async def test_send_command_success(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result()
    mock_naas_client.send_command.return_value = _mock_job(result)

    resp = await mcp_client.call_tool(
        "send_command",
        {
            "host": "192.168.1.1",
            "platform": "cisco_ios",
            "commands": ["show version"],
        },
    )

    mock_naas_client.send_command.assert_called_once_with(
        host="192.168.1.1",
        platform="cisco_ios",
        commands=["show version"],
    )
    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert data["job_id"] == "test-123"
    assert data["status"] == "finished"


async def test_send_command_with_optional_params(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result()
    mock_naas_client.send_command.return_value = _mock_job(result)

    await mcp_client.call_tool(
        "send_command",
        {
            "host": "10.0.0.1",
            "platform": "arista_eos",
            "commands": ["show ip bgp"],
            "username": "admin",
            "password": "secret",
            "enable": "enable_pass",
            "port": 2222,
            "tags": {"env": "prod"},
        },
    )

    mock_naas_client.send_command.assert_called_once_with(
        host="10.0.0.1",
        platform="arista_eos",
        commands=["show ip bgp"],
        username="admin",
        password="secret",
        enable="enable_pass",
        port=2222,
        tags={"env": "prod"},
    )


async def test_send_command_job_error(mcp_client: Client, mock_naas_client: AsyncMock):
    job = AsyncMock()
    job.wait = AsyncMock(
        side_effect=NaasConnectionError(
            "j1",
            "Connection timed out",
            error_code="CONNECTION_TIMEOUT",
            error_retryable=True,
        )
    )
    mock_naas_client.send_command.return_value = job

    resp = await mcp_client.call_tool(
        "send_command",
        {
            "host": "10.0.0.1",
            "platform": "cisco_ios",
            "commands": ["show version"],
        },
        raise_on_error=False,
    )

    assert resp.is_error is True


async def test_send_command_timeout(mcp_client: Client, mock_naas_client: AsyncMock):
    job = AsyncMock()
    job.wait = AsyncMock(side_effect=NaasTimeoutError("Job did not complete within 5s"))
    mock_naas_client.send_command.return_value = job

    resp = await mcp_client.call_tool(
        "send_command",
        {
            "host": "10.0.0.1",
            "platform": "cisco_ios",
            "commands": ["show version"],
        },
        raise_on_error=False,
    )

    assert resp.is_error is True


# -- send_config --


async def test_send_config_success(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result(results={"config_set_output": "hostname SWITCH-01"})
    mock_naas_client.send_config.return_value = _mock_job(result)

    resp = await mcp_client.call_tool(
        "send_config",
        {
            "host": "192.168.1.1",
            "platform": "cisco_ios",
            "commands": ["hostname SWITCH-01"],
        },
    )

    mock_naas_client.send_config.assert_called_once_with(
        host="192.168.1.1",
        platform="cisco_ios",
        commands=["hostname SWITCH-01"],
    )
    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert data["status"] == "finished"


async def test_send_config_with_commit_and_save(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result()
    mock_naas_client.send_config.return_value = _mock_job(result)

    await mcp_client.call_tool(
        "send_config",
        {
            "host": "10.0.0.1",
            "platform": "juniper_junos",
            "commands": ["set system hostname ROUTER-01"],
            "commit": True,
            "save_config": True,
        },
    )

    mock_naas_client.send_config.assert_called_once_with(
        host="10.0.0.1",
        platform="juniper_junos",
        commands=["set system hostname ROUTER-01"],
        commit=True,
        save_config=True,
    )


async def test_send_config_with_all_optional_params(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result()
    mock_naas_client.send_config.return_value = _mock_job(result)

    await mcp_client.call_tool(
        "send_config",
        {
            "host": "10.0.0.1",
            "platform": "cisco_ios",
            "commands": ["hostname R1"],
            "username": "admin",
            "password": "pass",
            "enable": "en",
            "port": 22,
            "commit": True,
            "save_config": True,
            "tags": {"env": "lab"},
        },
    )

    mock_naas_client.send_config.assert_called_once_with(
        host="10.0.0.1",
        platform="cisco_ios",
        commands=["hostname R1"],
        username="admin",
        password="pass",
        enable="en",
        port=22,
        commit=True,
        save_config=True,
        tags={"env": "lab"},
    )


# -- get_job_result --


async def test_get_job_result_success(mcp_client: Client, mock_naas_client: AsyncMock):
    result = _finished_result()
    mock_naas_client.get_command_result.return_value = result

    resp = await mcp_client.call_tool("get_job_result", {"job_id": "test-123"})

    mock_naas_client.get_command_result.assert_called_once_with("test-123")
    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert data["job_id"] == "test-123"


async def test_get_job_result_not_found(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.get_command_result.side_effect = NaasApiError(404, "Not Found")

    resp = await mcp_client.call_tool("get_job_result", {"job_id": "nonexistent"}, raise_on_error=False)

    assert resp.is_error is True


# -- cancel_job --


async def test_cancel_job_success(mcp_client: Client, mock_naas_client: AsyncMock):
    resp = await mcp_client.call_tool("cancel_job", {"job_id": "test-123"})

    mock_naas_client.cancel_job.assert_called_once_with("test-123")
    assert "cancelled" in resp.content[0].text.lower()  # type: ignore[union-attr]


async def test_cancel_job_not_found(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.cancel_job.side_effect = NaasApiError(404, "Not Found")

    resp = await mcp_client.call_tool("cancel_job", {"job_id": "nonexistent"}, raise_on_error=False)

    assert resp.is_error is True


# -- list_jobs --


async def test_list_jobs_defaults(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.list_jobs.return_value = ListJobsResponse.model_validate(
        {
            "jobs": [],
            "pagination": {"page": 1, "per_page": 20, "total": 0, "pages": 0},
        }
    )

    resp = await mcp_client.call_tool("list_jobs", {})

    mock_naas_client.list_jobs.assert_called_once_with(page=1, per_page=20, status=None)
    data = json.loads(resp.content[0].text)  # type: ignore[union-attr]
    assert data["jobs"] == []


async def test_list_jobs_with_filters(mcp_client: Client, mock_naas_client: AsyncMock):
    mock_naas_client.list_jobs.return_value = ListJobsResponse.model_validate(
        {
            "jobs": [],
            "pagination": {"page": 2, "per_page": 5, "total": 10, "pages": 2},
        }
    )

    await mcp_client.call_tool("list_jobs", {"page": 2, "per_page": 5, "status": "failed"})

    mock_naas_client.list_jobs.assert_called_once_with(page=2, per_page=5, status="failed")
