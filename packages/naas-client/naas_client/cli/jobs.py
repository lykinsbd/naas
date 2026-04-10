"""Jobs CLI subcommand group."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from naas_client.cli.output import auto_formatter
from naas_client.exceptions import NaasApiError
from naas_client.models import JobStatus

if TYPE_CHECKING:
    from naas_client.cli.config import CliConfig

jobs_app = typer.Typer(name="jobs", help="Job management commands")


@jobs_app.command("list")
def list_jobs(
    ctx: typer.Context,
    status: Annotated[
        str | None, typer.Option("--status", "-s", help="Filter: queued, started, finished, failed")
    ] = None,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag (key:value)")] = None,
    page: Annotated[int, typer.Option("--page", help="Page number")] = 1,
    per_page: Annotated[int, typer.Option("--per-page", help="Results per page")] = 20,
) -> None:
    """List jobs with pagination and filtering."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        result = client.list_jobs(page=page, per_page=per_page, status=status, tag=tag)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.jobs_list(result))


@jobs_app.command("get")
def get_job(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID")],
) -> None:
    """Get job status and results."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        result = client.get_command_result(job_id)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.job_result(result))

    if result.status == JobStatus.FAILED:
        raise typer.Exit(1)


@jobs_app.command("cancel")
def cancel_job(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID")],
) -> None:
    """Cancel a queued or running job."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        client.cancel_job(job_id)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.message(f"Job {job_id} cancelled"))


@jobs_app.command("replay")
def replay_job(
    ctx: typer.Context,
    job_id: Annotated[str, typer.Argument(help="Job ID")],
) -> None:
    """Re-enqueue a failed job."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        submission = client.replay_job(job_id)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.job_submitted(submission.job_id))


@jobs_app.command("failed")
def failed_jobs(ctx: typer.Context) -> None:
    """List failed jobs."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        result = client.failed_jobs()
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.failed_jobs(result))
