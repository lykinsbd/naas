"""
OpenTelemetry bootstrap module.

Gated by OTEL_ENABLED env var (default: false). When disabled, all public
functions are safe no-ops that never import opentelemetry packages.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

OTEL_ENABLED: bool = os.environ.get("OTEL_ENABLED", "false").lower() == "true"


def init_telemetry(service_name: str = "naas") -> None:
    """Initialize the TracerProvider. Call once at process startup."""
    if not OTEL_ENABLED:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


def inject_traceparent(meta: dict) -> dict:
    """Inject current trace context as a traceparent string into job metadata."""
    if not OTEL_ENABLED:
        return meta
    from opentelemetry.context import get_current
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier, context=get_current())
    if "traceparent" in carrier:
        meta["traceparent"] = carrier["traceparent"]
    return meta


def extract_context(meta: dict) -> Any:
    """Extract trace context from job metadata. Returns an OTel Context or None."""
    if not OTEL_ENABLED or "traceparent" not in meta:
        return None
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    return TraceContextTextMapPropagator().extract(carrier={"traceparent": meta["traceparent"]})


@contextmanager
def span(name: str, attributes: dict[str, str] | None = None, parent_context: Any = None) -> Iterator[Any]:
    """Start a span, optionally linking to a parent context extracted from job metadata."""
    if not OTEL_ENABLED:
        yield None
        return

    from opentelemetry import context, trace

    tracer = trace.get_tracer("naas")
    ctx_token = None
    if parent_context is not None:
        ctx_token = context.attach(parent_context)
    try:
        with tracer.start_as_current_span(
            name, attributes=attributes, record_exception=True, set_status_on_exception=True
        ) as s:
            yield s
    finally:
        if ctx_token is not None:
            context.detach(ctx_token)
