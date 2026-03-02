"""Tests for audit event logging."""

import logging

import pytest

from naas.library.audit import emit_audit_event


class TestAuditEvents:
    """Test audit event emission and validation."""

    def test_job_submitted_valid(self, caplog):
        """Test job.submitted event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event(
            "job.submitted",
            ip="192.168.1.1",
            platform="cisco_ios",
            port=22,
            command_count=3,
            user_hash="abc123",
            request_id="test-id",
        )
        assert "Audit event" in caplog.text

    def test_job_completed_valid(self, caplog):
        """Test job.completed event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event("job.completed", request_id="test-id", status="finished", duration_ms=1500)
        assert "Audit event" in caplog.text

    def test_job_cancelled_valid(self, caplog):
        """Test job.cancelled event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event("job.cancelled", request_id="test-id", cancelled_by_hash="xyz789")
        assert "Audit event" in caplog.text

    def test_device_locked_out_valid(self, caplog):
        """Test device.locked_out event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event("device.locked_out", ip="192.168.1.1", failure_count=10)
        assert "Audit event" in caplog.text

    def test_circuit_opened_valid(self, caplog):
        """Test circuit.opened event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event("circuit.opened", ip="192.168.1.1")
        assert "Audit event" in caplog.text

    def test_circuit_closed_valid(self, caplog):
        """Test circuit.closed event with all required fields."""
        caplog.set_level(logging.INFO)
        emit_audit_event("circuit.closed", ip="192.168.1.1")
        assert "Audit event" in caplog.text

    def test_unknown_event_type(self):
        """Test that unknown event types raise ValueError."""
        with pytest.raises(ValueError, match="Unknown audit event type"):
            emit_audit_event("unknown.event", field="value")

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValueError."""
        with pytest.raises(ValueError, match="Missing required fields"):
            emit_audit_event("job.submitted", ip="192.168.1.1")
