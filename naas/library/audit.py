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
    "job.submitted": {"host", "platform", "port", "command_count", "user_hash", "request_id"},
    "job.completed": {"request_id", "status", "duration_ms"},
    "job.cancelled": {"request_id", "cancelled_by_hash"},
    "job.orphaned": {"request_id", "worker_name"},
    "device.locked_out": {"host", "failure_count"},
    "circuit.opened": {"host"},
    "circuit.closed": {"host"},
}


def emit_audit_event(event_type: str, **fields: str | int) -> None:
    """
    Emit a structured audit event at INFO level.

    Args:
        event_type: Type of audit event. Must be one of:
            - ``job.submitted``: ip, platform, port, command_count, user_hash, request_id
            - ``job.completed``: request_id, status, duration_ms
            - ``job.cancelled``: request_id, cancelled_by_hash
            - ``device.locked_out``: ip, failure_count
            - ``circuit.opened``: ip
            - ``circuit.closed``: ip
        **fields: Event-specific fields as listed above.

    Raises:
        ValueError: If event_type is unknown or required fields are missing.
    """
    if event_type not in _EVENT_SCHEMAS:
        raise ValueError(f"Unknown audit event type: {event_type}")

    required = _EVENT_SCHEMAS[event_type]
    provided = set(fields.keys())
    missing = required - provided

    if missing:
        raise ValueError(f"Missing required fields for {event_type}: {missing}")

    logger.info("Audit event", extra={"event_type": event_type, **fields})
