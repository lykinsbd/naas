# ADR 0008: OpenTelemetry Instrumentation Strategy

* Status: Accepted
* Date: 2026-04-13

## Context and Problem Statement

NAAS has correlation IDs in logs but no distributed tracing. A request flows through API → Redis queue → worker → netmiko SSH, and there is no way to visualize this lifecycle in a trace viewer or correlate API latency with device connection time.

How should we add distributed tracing without impacting users who don't need it?

## Decision Drivers

* Zero overhead when tracing is disabled (most deployments won't use it initially)
* Trace context must survive the Redis/RQ queue boundary (API and worker are separate processes)
* Must not add hard dependencies — OTel packages are large and not needed by everyone
* Must be testable without running an OTLP collector

## Considered Options

* **Option 1**: OpenTelemetry as an optional dependency, gated by `OTEL_ENABLED`
* **Option 2**: OpenTelemetry as a required dependency, always initialized
* **Option 3**: Custom tracing with structured log correlation only

## Decision Outcome

Chosen option: **Option 1 — optional dependency gated by env var**, because it adds zero overhead for users who don't need tracing, follows the OTel SDK's own recommendation for optional instrumentation, and keeps the install size small for the common case.

### Consequences

* Good: Zero runtime cost when disabled — no OTel imports, no tracer initialization
* Good: `pip install naas[otel]` opts in explicitly
* Good: Trace context propagates through RQ via W3C `traceparent` in job metadata
* Bad: Two code paths (enabled/disabled) require testing both
* Bad: Flask auto-instrumentation import at module level requires `pragma: no cover`

## Pros and Cons of the Options

### Option 1: Optional dependency, gated by OTEL_ENABLED

* Good: Zero overhead when disabled — all functions are no-ops that never import OTel
* Good: Standard W3C trace context propagation
* Good: Users opt in with `pip install naas[otel]` and `OTEL_ENABLED=true`
* Bad: Conditional imports add complexity to the bootstrap module

### Option 2: Required dependency, always initialized

* Good: Simpler code — no conditional paths
* Bad: Adds ~15MB of dependencies for all users
* Bad: OTel SDK initialization has measurable startup cost even with no-op exporter
* Bad: Forces dependency on gRPC/protobuf for OTLP exporter

### Option 3: Custom tracing with structured logs

* Good: No new dependencies
* Good: Works with existing log infrastructure
* Bad: No standard trace format — can't use Jaeger, Zipkin, or Grafana Tempo
* Bad: No parent-child span relationships across the queue boundary
* Bad: Reinvents what OTel already solves

## Implementation Details

### Trace context propagation through RQ

The API injects a W3C `traceparent` string into the RQ job's `meta` dict at enqueue time. The worker extracts it and creates a child span linked to the API span. This gives a single trace ID across the full request lifecycle.

### Span hierarchy

```text
Flask HTTP span (auto-instrumented)
  └── naas.worker.execute (worker picks up job)
        ├── naas.netmiko.connect (SSH connection)
        └── naas.netmiko.send_command (per command)
            or naas.netmiko.send_config (config set)
```

### Testing approach

Unit tests use `InMemorySpanExporter` from `opentelemetry-test-utils` to capture spans in-memory and assert on names, attributes, parent-child relationships, and exception recording. Both enabled and disabled paths are tested.
