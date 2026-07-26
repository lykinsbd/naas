"""Structured audit event logging for compliance tracking."""

import logging

logger = logging.getLogger("NAAS")

_EVENT_SCHEMAS = {
    "auth.success": {"method", "identity"},
    "auth.failure": {"method", "reason"},
    "auth.context_denied": {"identity", "context", "allowed_contexts"},
    "auth.rbac_denied": {"identity", "role", "required_role", "endpoint"},
    "apikey.created": {"key_id", "role", "contexts", "created_by"},
    "apikey.revoked": {"key_id", "revoked_by"},
    "apikey.rotated": {"old_key_id", "new_key_id", "rotated_by"},
    "webhook.failed": {"job_id", "webhook_url", "attempts", "last_error"},
    "job.submitted": {"host", "platform", "port", "command_count", "user_hash", "request_id"},
    "job.completed": {"request_id", "status", "duration_ms"},
    "job.cancelled": {"request_id", "cancelled_by_hash"},
    "job.orphaned": {"request_id", "worker_name"},
    "device.locked_out": {"host", "failure_count"},
    "circuit.opened": {"host"},
    "circuit.closed": {"host"},
    "batch.submitted": {"batch_id", "device_count", "operation"},
}


def emit_audit_event(event_type: str, **fields: str | int) -> None:
    """Emit a structured audit event at INFO level.

    Args:
        event_type: Event type key from ``_EVENT_SCHEMAS``.
        **fields: Required fields for the given event type.

    Raises:
        ValueError: If event_type is unknown or required fields are missing.

    Valid event types and their required fields are defined in
    ``_EVENT_SCHEMAS`` at the top of this module.
    """
    if event_type not in _EVENT_SCHEMAS:
        raise ValueError(f"Unknown audit event type: {event_type}")

    required = _EVENT_SCHEMAS[event_type]
    provided = set(fields.keys())
    missing = required - provided

    if missing:
        raise ValueError(f"Missing required fields for {event_type}: {missing}")

    logger.info("Audit event", extra={"event_type": event_type, **fields})
