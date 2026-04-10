"""NAAS CLI — command-line interface for NAAS (Netmiko As A Service)."""

from __future__ import annotations

from typing import Annotated

import typer

from naas_client.cli.config import CliConfig
from naas_client.cli.output import auto_formatter
from naas_client.client import NaasClient
from naas_client.exceptions import NaasApiError, NaasAuthError

app = typer.Typer(
    name="naas",
    help="CLI for NAAS (Netmiko As A Service)",
    no_args_is_help=True,
)

# Register subcommands
from naas_client.cli.commands import commands_app  # noqa: E402

app.registered_commands += commands_app.registered_commands

_UrlOpt = Annotated[str | None, typer.Option("--url", envvar="NAAS_URL", help="NAAS server URL")]
_UsernameOpt = Annotated[str | None, typer.Option("--username", envvar="NAAS_USERNAME", help="Basic auth username")]
_PasswordOpt = Annotated[str | None, typer.Option("--password", envvar="NAAS_PASSWORD", help="Basic auth password")]
_ApiKeyOpt = Annotated[str | None, typer.Option("--api-key", envvar="NAAS_API_KEY", help="JWT API key")]
_NoVerifyOpt = Annotated[bool, typer.Option("--no-verify", help="Disable TLS verification")]
_FormatOpt = Annotated[str | None, typer.Option("--format", "-f", help="Output format: json or table")]
_QuietOpt = Annotated[bool, typer.Option("--quiet", "-q", help="Suppress non-essential output")]


def _version_callback(value: bool) -> None:
    if value:
        from naas_client import __version__

        typer.echo(f"naas-client {__version__}")
        raise typer.Exit()


def _get_client(ctx: typer.Context) -> NaasClient:
    """Build a NaasClient from resolved config."""
    cfg: CliConfig = ctx.obj
    if not cfg.url:
        typer.echo("Error: NAAS URL required. Set --url, NAAS_URL, or url in config file.", err=True)
        raise typer.Exit(2)
    return NaasClient(
        cfg.url,
        username=cfg.username,
        password=cfg.password,
        api_key=cfg.api_key,
        verify=cfg.verify,
        timeout=cfg.timeout,
    )


def _handle_error(e: NaasApiError, cfg: CliConfig) -> None:
    """Print error and exit with appropriate code."""
    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.error(str(e), e.status_code), err=True)
    code = 3 if isinstance(e, NaasAuthError) else 2
    raise typer.Exit(code)


@app.callback()
def main(
    ctx: typer.Context,
    url: _UrlOpt = None,
    username: _UsernameOpt = None,
    password: _PasswordOpt = None,
    api_key: _ApiKeyOpt = None,
    no_verify: _NoVerifyOpt = False,
    fmt: _FormatOpt = None,
    quiet: _QuietOpt = False,
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version")
    ] = False,
) -> None:
    """NAAS CLI — command-line interface for NAAS (Netmiko As A Service)."""
    cfg = CliConfig.load()

    if url is not None:
        cfg.url = url
    if username is not None:
        cfg.username = username
    if password is not None:
        cfg.password = password
    if api_key is not None:
        cfg.api_key = api_key
    if no_verify:
        cfg.verify = False
    if fmt is not None:
        cfg.format = fmt  # type: ignore[assignment]

    ctx.obj = cfg


@app.command()
def healthcheck(ctx: typer.Context) -> None:
    """Check NAAS server health."""
    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        health = client.healthcheck()
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.healthcheck(health))
