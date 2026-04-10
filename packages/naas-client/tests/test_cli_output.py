"""Tests for output formatters."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from naas_client.cli.output import HumanFormatter, JsonFormatter, auto_formatter
from naas_client.models import HealthCheckResponse

if TYPE_CHECKING:
    import pytest

HEALTH_DATA = HealthCheckResponse.model_validate(
    {
        "status": "healthy",
        "version": "2.0.0",
        "uptime_seconds": 100,
        "components": {
            "redis": {"status": "healthy"},
            "queue": {"status": "healthy", "depth": 0},
            "workers": {"status": "healthy", "count": 4, "active_jobs": 0},
            "failed_jobs": 0,
        },
    }
)


class TestJsonFormatter:
    def test_healthcheck(self) -> None:
        out = JsonFormatter().healthcheck(HEALTH_DATA)
        assert '"healthy"' in out

    def test_error(self) -> None:
        out = JsonFormatter().error("bad", 500)
        assert "500" in out

    def test_error_no_code(self) -> None:
        out = JsonFormatter().error("bad")
        assert "status_code" not in out

    def test_message(self) -> None:
        out = JsonFormatter().message("hello")
        assert '"hello"' in out

    def test_job_submitted(self) -> None:
        assert "abc-123" in JsonFormatter().job_submitted("abc-123")

    def test_waiting_empty(self) -> None:
        assert JsonFormatter().waiting("abc-123") == ""

    def test_job_result(self) -> None:
        from naas_client.models import JobResult

        r = JobResult.model_validate({"job_id": "abc-123", "status": "finished", "results": {"show version": "Cisco"}})
        out = JsonFormatter().job_result(r)
        assert "finished" in out

    def test_job_error(self) -> None:
        out = JsonFormatter().job_error("abc-123", "Connection refused")
        assert "failed" in out


class TestHumanFormatter:
    def test_healthcheck(self) -> None:
        out = HumanFormatter().healthcheck(HEALTH_DATA)
        assert "healthy" in out

    def test_error(self) -> None:
        out = HumanFormatter().error("bad", 500)
        assert "500" in out

    def test_error_no_code(self) -> None:
        out = HumanFormatter().error("bad")
        assert "Error" in out

    def test_message(self) -> None:
        assert HumanFormatter().message("hello") == "hello"

    def test_job_submitted(self) -> None:
        assert "abc-123" in HumanFormatter().job_submitted("abc-123")

    def test_waiting(self) -> None:
        assert "abc-123" in HumanFormatter().waiting("abc-123")

    def test_job_result_finished(self) -> None:
        from naas_client.models import JobResult

        r = JobResult.model_validate({"job_id": "abc-123", "status": "finished", "results": {"show version": "Cisco"}})
        out = HumanFormatter().job_result(r)
        assert "✓" in out
        assert "Cisco" in out

    def test_job_result_failed(self) -> None:
        from naas_client.models import JobResult

        r = JobResult.model_validate({"job_id": "abc-123", "status": "failed", "error": "timeout"})
        out = HumanFormatter().job_result(r)
        assert "✗" in out
        assert "timeout" in out

    def test_job_error(self) -> None:
        out = HumanFormatter().job_error("abc-123", "Connection refused")
        assert "failed" in out


class TestAutoFormatter:
    def test_explicit_json(self) -> None:
        assert isinstance(auto_formatter("json"), JsonFormatter)

    def test_explicit_table(self) -> None:
        assert isinstance(auto_formatter("table"), HumanFormatter)

    def test_auto_non_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        assert isinstance(auto_formatter(), JsonFormatter)

    def test_auto_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert isinstance(auto_formatter(), HumanFormatter)
