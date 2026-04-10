"""Output formatters for human and JSON modes."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from naas_client.models import HealthCheckResponse


class Formatter(Protocol):
    """Output formatter protocol."""

    def healthcheck(self, data: HealthCheckResponse) -> str: ...
    def error(self, message: str, status_code: int | None = None) -> str: ...
    def message(self, text: str) -> str: ...


class JsonFormatter:
    """Machine-readable JSON output."""

    def healthcheck(self, data: HealthCheckResponse) -> str:
        return data.model_dump_json(indent=2)

    def error(self, message: str, status_code: int | None = None) -> str:
        d: dict[str, Any] = {"error": message}
        if status_code is not None:
            d["status_code"] = status_code
        return json.dumps(d, indent=2)

    def message(self, text: str) -> str:
        return json.dumps({"message": text}, indent=2)


class HumanFormatter:
    """Human-readable Rich output."""

    def healthcheck(self, data: HealthCheckResponse) -> str:
        from rich.table import Table

        status_icon = "●" if data.status == "healthy" else "○"
        table = Table(show_header=True, header_style="bold")
        table.add_column("Status")
        table.add_column("Version")
        table.add_column("Uptime")
        table.add_column("Workers")
        table.add_column("Queue")
        table.add_column("Failed")

        workers = data.components.workers
        queue = data.components.queue
        table.add_row(
            f"{status_icon} {data.status}",
            data.version,
            f"{data.uptime_seconds}s",
            str(workers.count if workers.count is not None else "?"),
            str(queue.depth if queue.depth is not None else "?"),
            str(data.components.failed_jobs or 0),
        )

        from io import StringIO

        from rich.console import Console

        buf = StringIO()
        Console(file=buf, force_terminal=True).print(table)
        return buf.getvalue().rstrip()

    def error(self, message: str, status_code: int | None = None) -> str:
        prefix = f"Error ({status_code})" if status_code else "Error"
        return f"✗ {prefix}: {message}"

    def message(self, text: str) -> str:
        return text


def auto_formatter(fmt: str | None = None) -> Formatter:
    """Select formatter based on explicit format or TTY detection."""
    if fmt == "json":
        return JsonFormatter()
    if fmt == "table":
        return HumanFormatter()
    # Auto-detect: human for TTY, JSON for pipes
    if sys.stdout.isatty():
        return HumanFormatter()
    return JsonFormatter()
