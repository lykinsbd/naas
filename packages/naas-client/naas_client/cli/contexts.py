"""Contexts CLI subcommand."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from naas_client.cli.output import auto_formatter
from naas_client.exceptions import NaasApiError

if TYPE_CHECKING:
    from naas_client.cli.config import CliConfig

contexts_app = typer.Typer(name="contexts", help="Routing context commands")


@contexts_app.command("list")
def list_contexts(ctx: typer.Context) -> None:
    """List active routing contexts."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        result = client.list_contexts()
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.contexts_list(result))
