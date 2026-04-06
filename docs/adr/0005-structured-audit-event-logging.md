# Structured Audit Event Logging

* Status: Accepted
* Date: 2026-04-06

## Context and Problem Statement

NAAS emits structured audit events for compliance and security tracking via
`emit_audit_event()` in `naas/library/audit.py`. The system grew organically from
job lifecycle events and now needs to cover authentication, authorization, and key
management. Design decisions about log routing, identity representation, schema
enforcement, and data privacy need to be recorded before the event catalog grows
further.

## Decision Drivers

* Audit events must be machine-parseable for SIEM ingestion
* Sensitive data (credentials, command output) must never appear in audit logs
* Events must have consistent identity representation across auth methods
* Schema enforcement must prevent silent data loss in audit trails
* The pattern must be easy to extend for future features (webhooks, OpenTelemetry)

## Decision Outcome

Structured JSON events emitted via Python's `logging` module with schema validation
at emit time. All events flow through the existing `NAAS` logger to stdout. Routing,
retention, and tamper-evidence are deployment concerns, not application concerns.

## Design

### Log Routing

All audit events use the shared `NAAS` logger at INFO level. Audit events are
distinguished from operational logs by the presence of an `event_type` field in the
structured JSON output.

Operators who need separate audit log files or syslog forwarding configure this at
the deployment layer (additional Python logging handler, or log shipper filter on
`event_type`). The application does not manage log destinations.

**Rationale:** A separate `NAAS.audit` logger was considered but rejected — it adds
configuration complexity with no application-level benefit. The structured
`event_type` field is sufficient for filtering.

### Schema Validation

Every event type has a required field set defined in `_EVENT_SCHEMAS`. Calling
`emit_audit_event()` with a missing field raises `ValueError` immediately rather
than emitting an incomplete record.

**Rationale:** Audit trails with missing fields are worse than no audit trail — they
create false confidence. Fail-loud at emit time catches bugs in development rather
than discovering gaps during incident review.

### Identity Representation

| Auth method | `identity` value | Example |
| --- | --- | --- |
| Basic auth | Username from Authorization header | `"admin"` |
| Bearer JWT | Key ID from `sub` claim | `"k-a1b2c3d4e5f6"` |
| Unauthenticated | `"anonymous"` | `"anonymous"` |

Job-level events continue to use `user_hash` (salted SHA512 of credentials) for
backward compatibility and because job events correlate with device connections, not
API identity.

### Data Privacy

Audit events MUST NOT contain:

* Passwords, enable secrets, or API key tokens
* Command output or device responses
* Full request/response bodies

Audit events MAY contain:

* Usernames and key IDs (identity, not credentials)
* Host/IP being targeted
* Context, platform, port
* Command count (not command content)
* Job IDs and status

### Event Catalog

#### Authentication

| Event | Fields | Description |
| --- | --- | --- |
| `auth.success` | `method`, `identity` | Successful authentication |
| `auth.failure` | `method`, `reason` | Failed authentication attempt |

#### Authorization

| Event | Fields | Description |
| --- | --- | --- |
| `auth.context_denied` | `identity`, `context`, `allowed_contexts` | Context authorization failure |
| `auth.rbac_denied` | `identity`, `role`, `required_role`, `endpoint` | Role check failure |

#### API Key Management

| Event | Fields | Description |
| --- | --- | --- |
| `apikey.created` | `key_id`, `role`, `contexts`, `created_by` | New API key created |
| `apikey.revoked` | `key_id`, `revoked_by` | API key revoked |

#### Job Lifecycle (existing)

| Event | Fields | Description |
| --- | --- | --- |
| `job.submitted` | `host`, `platform`, `port`, `command_count`, `user_hash`, `request_id` | Job enqueued |
| `job.completed` | `request_id`, `status`, `duration_ms` | Job finished |
| `job.cancelled` | `request_id`, `cancelled_by_hash` | Job cancelled |
| `job.orphaned` | `request_id`, `worker_name` | Orphaned job reaped |

#### Device (existing)

| Event | Fields | Description |
| --- | --- | --- |
| `device.locked_out` | `host`, `failure_count` | Device locked out |
| `circuit.opened` | `host` | Circuit breaker opened |
| `circuit.closed` | `host` | Circuit breaker closed |

### Adding New Events

1. Add the event type and required fields to `_EVENT_SCHEMAS`
2. Call `emit_audit_event()` at the appropriate point
3. Add a unit test verifying the event is emitted with correct fields
4. Update this ADR's event catalog

### Deployment Guidance

* **SIEM integration:** Filter structured JSON logs on `event_type` field
* **Separate audit file:** Add a second `logging.FileHandler` to the `NAAS` logger
  with a filter on `event_type`
* **Tamper evidence:** Ship logs to an append-only store (S3, CloudWatch Logs)
* **Retention:** Configure via log rotation or cloud lifecycle policies
* **Alerting:** Key events to alert on: `auth.failure` (brute force),
  `auth.rbac_denied` (privilege escalation), `apikey.created`/`apikey.revoked`
  (key management)
