"""send-command and send-config CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from naas_client.cli.output import auto_formatter
from naas_client.exceptions import NaasApiError, NaasJobError, NaasTimeoutError

if TYPE_CHECKING:
    from naas_client.cli.config import CliConfig

commands_app = typer.Typer()


def _run_job(
    ctx: typer.Context,
    method: str,
    host: str,
    platform: str,
    args: list[str],
    port: int,
    wait: bool,
    timeout: float,
    context: str,
    save_config: bool = False,
    commit: bool = False,
    expect_string: str | None = None,
) -> None:
    """Submit a job and optionally wait for results."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    fmt = auto_formatter(cfg.format)

    payload: dict[str, object] = {
        "host": host,
        "platform": platform,
        "port": port,
        "context": context,
    }

    if method == "send_config":
        payload["config"] = args
        if save_config:
            payload["save_config"] = True
        if commit:
            payload["commit"] = True
    else:
        payload["commands"] = args
        if expect_string:
            payload["expect_string"] = expect_string

    try:
        job = client.send_config(**payload) if method == "send_config" else client.send_command(**payload)

        if not wait:
            typer.echo(fmt.job_submitted(job.job_id))
            return

        typer.echo(fmt.waiting(job.job_id), err=True)
        result = job.wait(timeout=timeout)
        typer.echo(fmt.job_result(result))

    except NaasJobError as e:
        typer.echo(fmt.job_error(e.job_id, e.error), err=True)
        raise typer.Exit(1) from None
    except NaasTimeoutError as e:
        typer.echo(fmt.error(str(e)), err=True)
        raise typer.Exit(4) from None
    except NaasApiError as e:
        _handle_error(e, cfg)
    finally:
        client.close()


@commands_app.command("send-command")
def send_command(
    ctx: typer.Context,
    commands: Annotated[list[str], typer.Argument(help="Commands to execute on the device")],
    host: Annotated[str, typer.Option("--host", "-h", help="Device hostname or IP")] = "",
    platform: Annotated[str, typer.Option("--platform", "-p", help="Netmiko platform")] = "cisco_ios",
    port: Annotated[int, typer.Option("--port", help="SSH port")] = 22,
    wait: Annotated[bool, typer.Option("--wait", "-w", help="Wait for job to complete")] = False,
    timeout: Annotated[float, typer.Option("--timeout", "-t", help="Wait timeout in seconds")] = 60.0,
    context: Annotated[str, typer.Option("--context", help="Routing context")] = "default",
    expect_string: Annotated[str | None, typer.Option("--expect-string", help="Regex to match in output")] = None,
) -> None:
    """Submit a send-command job to a network device."""
    if not host:
        typer.echo("Error: --host is required", err=True)
        raise typer.Exit(2)
    _run_job(ctx, "send_command", host, platform, commands, port, wait, timeout, context, expect_string=expect_string)


@commands_app.command("send-config")
def send_config(
    ctx: typer.Context,
    config_lines: Annotated[list[str], typer.Argument(help="Configuration lines to apply")],
    host: Annotated[str, typer.Option("--host", "-h", help="Device hostname or IP")] = "",
    platform: Annotated[str, typer.Option("--platform", "-p", help="Netmiko platform")] = "cisco_ios",
    port: Annotated[int, typer.Option("--port", help="SSH port")] = 22,
    wait: Annotated[bool, typer.Option("--wait", "-w", help="Wait for job to complete")] = False,
    timeout: Annotated[float, typer.Option("--timeout", "-t", help="Wait timeout in seconds")] = 60.0,
    context: Annotated[str, typer.Option("--context", help="Routing context")] = "default",
    save_config: Annotated[bool, typer.Option("--save-config", help="Save config after applying")] = False,
    commit: Annotated[bool, typer.Option("--commit", help="Commit config (Juniper)")] = False,
) -> None:
    """Submit a send-config job to a network device."""
    if not host:
        typer.echo("Error: --host is required", err=True)
        raise typer.Exit(2)
    _run_job(
        ctx,
        "send_config",
        host,
        platform,
        config_lines,
        port,
        wait,
        timeout,
        context,
        save_config=save_config,
        commit=commit,
    )
