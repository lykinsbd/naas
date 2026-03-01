"""Structured audit event logging for compliance tracking."""

import logging

logger = logging.getLogger("NAAS")

_EVENT_SCHEMAS = {
    "job.submitted": {"ip", "platform", "port", "command_count", "user_hash", "request_id"},
    "job.completed": {"request_id", "status", "duration_ms"},
    "job.cancelled": {"request_id", "cancelled_by_hash"},
    "device.locked_out": {"ip", "failure_count"},
    "circuit.opened": {"ip"},
    "circuit.closed": {"ip"},
}


def emit_audit_event(event_type: str, **fields: str | int) -> None:
    """
    Emit a structured audit event at INFO level.

    Args:
        event_type: Type of audit event (e.g., "job.submitted").
        **fields: Event-specific fields as defined in schema.

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
