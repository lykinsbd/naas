"""MCP tools for NAAS operations."""

from typing import Any

from fastmcp import Context
from naas_client import AsyncNaasClient

from naas_mcp.server import mcp


def _client(ctx: Context) -> AsyncNaasClient:
    return ctx.lifespan_context["client"]  # type: ignore[return-value]


def _job_poll_interval(ctx: Context) -> float:
    return ctx.lifespan_context["job_poll_interval"]  # type: ignore[return-value]


def _job_timeout(ctx: Context) -> float:
    return ctx.lifespan_context["job_timeout"]  # type: ignore[return-value]


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON-serializable dict."""
    return result.model_dump(mode="json")  # type: ignore[no-any-return]


@mcp.tool
async def send_command(
    ctx: Context,
    host: str,
    platform: str,
    commands: list[str],
    username: str | None = None,
    password: str | None = None,
    enable: str | None = None,
    port: int | None = None,
    tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send show/read commands to a network device and wait for results.

    Args:
        host: Device hostname or IP address.
        platform: Netmiko platform type (e.g. cisco_ios, arista_eos).
        commands: List of commands to execute.
        username: Device username (optional if NAAS has defaults).
        password: Device password.
        enable: Enable/privilege password.
        port: SSH port (default 22).
        tags: Optional key-value tags for the job.
    """
    kwargs: dict[str, Any] = {"host": host, "platform": platform, "commands": commands}
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password
    if enable is not None:
        kwargs["enable"] = enable
    if port is not None:
        kwargs["port"] = port
    if tags is not None:
        kwargs["tags"] = tags

    job = await _client(ctx).send_command(**kwargs)
    result = await job.wait(timeout=_job_timeout(ctx), interval=_job_poll_interval(ctx))
    return _result_to_dict(result)


@mcp.tool
async def send_config(
    ctx: Context,
    host: str,
    platform: str,
    commands: list[str],
    username: str | None = None,
    password: str | None = None,
    enable: str | None = None,
    port: int | None = None,
    commit: bool = False,
    save_config: bool = False,
    tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Push configuration commands to a network device and wait for results.

    Args:
        host: Device hostname or IP address.
        platform: Netmiko platform type (e.g. cisco_ios, arista_eos).
        commands: List of configuration commands.
        username: Device username.
        password: Device password.
        enable: Enable/privilege password.
        port: SSH port (default 22).
        commit: Commit config on platforms that support it (e.g. Junos).
        save_config: Save running config to startup after applying.
        tags: Optional key-value tags for the job.
    """
    kwargs: dict[str, Any] = {"host": host, "platform": platform, "commands": commands}
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password
    if enable is not None:
        kwargs["enable"] = enable
    if port is not None:
        kwargs["port"] = port
    if commit:
        kwargs["commit"] = commit
    if save_config:
        kwargs["save_config"] = save_config
    if tags is not None:
        kwargs["tags"] = tags

    job = await _client(ctx).send_config(**kwargs)
    result = await job.wait(timeout=_job_timeout(ctx), interval=_job_poll_interval(ctx))
    return _result_to_dict(result)


@mcp.tool
async def get_job_result(ctx: Context, job_id: str) -> dict[str, Any]:
    """Get the result of a previously submitted job.

    Args:
        job_id: The job ID returned from send_command or send_config.
    """
    result = await _client(ctx).get_command_result(job_id)
    return _result_to_dict(result)


@mcp.tool
async def cancel_job(ctx: Context, job_id: str) -> str:
    """Cancel a queued or running job.

    Args:
        job_id: The job ID to cancel.
    """
    await _client(ctx).cancel_job(job_id)
    return f"Job {job_id} cancelled."


@mcp.tool
async def list_jobs(
    ctx: Context,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    """List jobs with optional filtering.

    Args:
        page: Page number (default 1).
        per_page: Results per page (default 20).
        status: Filter by status (queued, started, finished, failed).
    """
    result = await _client(ctx).list_jobs(page=page, per_page=per_page, status=status)
    return _result_to_dict(result)
