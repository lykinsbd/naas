"""Ensure every CLI command has integration test coverage.

If you add a new CLI command, add it to _COVERED_COMMANDS below
and write an integration test for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from naas_client.cli import app

if TYPE_CHECKING:
    import typer

# Every command path that MUST have an integration test.
# Format: ("group", "subcommand") or ("command",) for top-level.
_COVERED_COMMANDS: set[str] = {
    "healthcheck",
    "send-command",
    "send-config",
    "jobs list",
    "jobs get",
    "jobs cancel",
    "jobs replay",
    "jobs failed",
    "contexts list",
    "api-keys list",
    "api-keys create",
    "api-keys delete",
    "api-keys rotate",
}


def _collect_commands(typer_app: typer.Typer, prefix: str = "") -> set[str]:
    """Recursively collect all command paths from a Typer app."""
    commands: set[str] = set()
    for cmd in typer_app.registered_commands:
        name = cmd.name or (cmd.callback.__name__.replace("_", "-") if cmd.callback else "")
        path = f"{prefix} {name}".strip() if prefix else name
        commands.add(path)
    for group in typer_app.registered_groups:
        ti = group.typer_instance
        if ti:
            group_name = ti.info.name if ti.info and ti.info.name else ""
            sub_prefix = f"{prefix} {group_name}".strip() if prefix else group_name
            commands |= _collect_commands(ti, sub_prefix)
    return commands


class TestCliCommandCoverage:
    def test_all_commands_have_integration_coverage(self) -> None:
        """Every registered CLI command must be in _COVERED_COMMANDS."""
        registered = _collect_commands(app)
        uncovered = registered - _COVERED_COMMANDS
        assert not uncovered, (
            "CLI commands missing from _COVERED_COMMANDS:\n"
            + "\n".join(f"  - {c}" for c in sorted(uncovered))
            + "\n\nAdd them to _COVERED_COMMANDS and write integration tests."
        )

    def test_no_stale_entries(self) -> None:
        """_COVERED_COMMANDS shouldn't list commands that don't exist."""
        registered = _collect_commands(app)
        stale = _COVERED_COMMANDS - registered
        assert not stale, "Stale entries in _COVERED_COMMANDS (commands no longer exist):\n" + "\n".join(
            f"  - {c}" for c in sorted(stale)
        )
