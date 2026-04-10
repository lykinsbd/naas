"""API keys CLI subcommand group."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from naas_client.cli.output import auto_formatter
from naas_client.exceptions import NaasApiError

if TYPE_CHECKING:
    from naas_client.cli.config import CliConfig

api_keys_app = typer.Typer(name="api-keys", help="API key management commands")


@api_keys_app.command("list")
def list_api_keys(ctx: typer.Context) -> None:
    """List active API keys (metadata only)."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        keys = client.list_api_keys()
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.api_keys_list(keys))


@api_keys_app.command("create")
def create_api_key(
    ctx: typer.Context,
    role: Annotated[str, typer.Option("--role", "-r", help="Key role")] = "admin",
    contexts: Annotated[str | None, typer.Option("--contexts", "-c", help="Comma-separated contexts")] = None,
    ttl: Annotated[int | None, typer.Option("--ttl", help="TTL in seconds")] = None,
) -> None:
    """Create a new API key."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    ctx_list = [c.strip() for c in contexts.split(",")] if contexts else None
    try:
        result = client.create_api_key(role=role, contexts=ctx_list, ttl=ttl)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.api_key_created(result))


@api_keys_app.command("delete")
def delete_api_key(
    ctx: typer.Context,
    key_id: Annotated[str, typer.Argument(help="Key ID to revoke")],
) -> None:
    """Revoke an API key."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        client.delete_api_key(key_id)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.message(f"API key {key_id} revoked"))


@api_keys_app.command("rotate")
def rotate_api_key(
    ctx: typer.Context,
    key_id: Annotated[str, typer.Argument(help="Key ID to rotate")],
) -> None:
    """Rotate an API key. Returns a new token."""
    from naas_client.cli import _get_client, _handle_error

    cfg: CliConfig = ctx.obj
    client = _get_client(ctx)
    try:
        result = client.rotate_api_key(key_id)
    except NaasApiError as e:
        _handle_error(e, cfg)
        return  # pragma: no cover
    finally:
        client.close()

    fmt = auto_formatter(cfg.format)
    typer.echo(fmt.api_key_created(result))
