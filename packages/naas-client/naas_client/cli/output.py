"""Output formatters for human and JSON modes."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from naas_client.models import (
        ApiKeyCreateResponse,
        ApiKeyListItem,
        ContextsResponse,
        FailedJobsResponse,
        HealthCheckResponse,
        JobResult,
        ListJobsResponse,
    )


class Formatter(Protocol):
    """Output formatter protocol."""

    def healthcheck(self, data: HealthCheckResponse) -> str: ...
    def error(self, message: str, status_code: int | None = None) -> str: ...
    def message(self, text: str) -> str: ...
    def job_submitted(self, job_id: str) -> str: ...
    def waiting(self, job_id: str) -> str: ...
    def job_result(self, result: JobResult) -> str: ...
    def job_error(self, job_id: str, error: str) -> str: ...
    def jobs_list(self, data: ListJobsResponse) -> str: ...
    def failed_jobs(self, data: FailedJobsResponse) -> str: ...
    def contexts_list(self, data: ContextsResponse) -> str: ...
    def api_keys_list(self, keys: list[ApiKeyListItem]) -> str: ...
    def api_key_created(self, data: ApiKeyCreateResponse) -> str: ...


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

    def job_submitted(self, job_id: str) -> str:
        return json.dumps({"job_id": job_id}, indent=2)

    def waiting(self, job_id: str) -> str:
        return ""

    def job_result(self, result: JobResult) -> str:
        return result.model_dump_json(indent=2)

    def job_error(self, job_id: str, error: str) -> str:
        return json.dumps({"job_id": job_id, "status": "failed", "error": error}, indent=2)

    def jobs_list(self, data: ListJobsResponse) -> str:
        return data.model_dump_json(indent=2)

    def failed_jobs(self, data: FailedJobsResponse) -> str:
        return data.model_dump_json(indent=2)

    def contexts_list(self, data: ContextsResponse) -> str:
        return data.model_dump_json(indent=2)

    def api_keys_list(self, keys: list[ApiKeyListItem]) -> str:
        return json.dumps([k.model_dump() for k in keys], indent=2)

    def api_key_created(self, data: ApiKeyCreateResponse) -> str:
        return data.model_dump_json(indent=2)


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

    def job_submitted(self, job_id: str) -> str:
        return f"Job submitted: {job_id}"

    def waiting(self, job_id: str) -> str:
        return f"⠋ Waiting for job {job_id}..."

    def job_result(self, result: JobResult) -> str:
        from naas_client.models import JobStatus

        icon = "✓" if result.status == JobStatus.FINISHED else "✗"
        lines = [f"{icon} Job {result.job_id}: {result.status}"]
        if result.results:
            for cmd, output in result.results.items():
                lines.append(f"\n{cmd}\n{'─' * len(cmd)}\n{output}")
        if result.error:
            lines.append(f"\nError: {result.error}")
        return "\n".join(lines)

    def job_error(self, job_id: str, error: str) -> str:
        return f"✗ Job {job_id} failed: {error}"

    def jobs_list(self, data: ListJobsResponse) -> str:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("Job ID")
        table.add_column("Status")
        table.add_column("Created")
        table.add_column("Tags")
        for j in data.jobs:
            table.add_row(j.job_id, j.status, j.created_at or "", str(j.tags or ""))
        buf = StringIO()
        Console(file=buf, force_terminal=True).print(table)
        p = data.pagination
        return f"{buf.getvalue().rstrip()}\nPage {p.page}/{p.pages} ({p.total} total)"

    def failed_jobs(self, data: FailedJobsResponse) -> str:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("Job ID")
        table.add_column("Host")
        table.add_column("Platform")
        table.add_column("Failed At")
        table.add_column("Error")
        for j in data.jobs:
            table.add_row(j.job_id, j.host or "", j.platform or "", j.failed_at or "", j.error or "")
        buf = StringIO()
        Console(file=buf, force_terminal=True).print(table)
        return f"{buf.getvalue().rstrip()}\n{data.total} failed job(s)"

    def contexts_list(self, data: ContextsResponse) -> str:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Workers")
        table.add_column("Queue Depth")
        for c in data.contexts:
            table.add_row(c.name, str(c.workers), str(c.queue_depth))
        buf = StringIO()
        Console(file=buf, force_terminal=True).print(table)
        return buf.getvalue().rstrip()

    def api_keys_list(self, keys: list[ApiKeyListItem]) -> str:
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("Key ID")
        table.add_column("Role")
        table.add_column("Contexts")
        table.add_column("Created")
        table.add_column("Expires")
        for k in keys:
            table.add_row(
                k.key_id,
                k.role,
                ", ".join(k.contexts or []),
                k.created_at,
                k.expires_at,
            )
        buf = StringIO()
        Console(file=buf, force_terminal=True).print(table)
        return buf.getvalue().rstrip()

    def api_key_created(self, data: ApiKeyCreateResponse) -> str:
        lines = [
            f"Key ID:  {data.key_id}",
            f"Role:    {data.role}",
            f"Token:   {data.token}",
            f"Expires: {data.expires_at}",
        ]
        return "\n".join(lines)


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
