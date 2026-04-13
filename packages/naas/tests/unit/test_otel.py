"""Tests for OpenTelemetry instrumentation module."""

import pytest


class TestOtelDisabled:
    """When OTEL_ENABLED=false, all functions are safe no-ops."""

    def test_init_telemetry_noop(self) -> None:
        from naas.library.otel import init_telemetry

        init_telemetry()  # Should not raise even without otel packages

    def test_inject_traceparent_noop(self) -> None:
        from naas.library.otel import inject_traceparent

        meta = {"context": "default"}
        result = inject_traceparent(meta)
        assert result == {"context": "default"}
        assert "traceparent" not in result

    def test_extract_context_noop(self) -> None:
        from naas.library.otel import extract_context

        assert extract_context({}) is None
        assert extract_context({"traceparent": "00-abc-def-01"}) is None

    def test_span_noop(self) -> None:
        from naas.library.otel import span

        with span("test.span", attributes={"key": "val"}) as s:
            assert s is None

    def test_span_noop_propagates_exception(self) -> None:
        from naas.library.otel import span

        with pytest.raises(ValueError, match="boom"):
            with span("test.span"):
                raise ValueError("boom")


@pytest.fixture()
def _enable_otel(monkeypatch):
    """Enable OTel and configure InMemorySpanExporter for testing."""
    monkeypatch.setenv("OTEL_ENABLED", "true")

    import naas.library.otel

    monkeypatch.setattr(naas.library.otel, "OTEL_ENABLED", True)

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.test.test_base import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Force-set provider even if one already exists
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
    trace.set_tracer_provider(provider)

    yield exporter

    exporter.clear()
    monkeypatch.setattr(naas.library.otel, "OTEL_ENABLED", False)


@pytest.mark.usefixtures("_enable_otel")
class TestOtelEnabled:
    """When OTEL_ENABLED=true, spans are created and context propagates."""

    def test_init_telemetry_sets_provider(self, _enable_otel, monkeypatch) -> None:
        import naas.library.otel

        monkeypatch.setattr(naas.library.otel, "OTEL_ENABLED", True)

        from opentelemetry import trace

        # Reset so init_telemetry can set a fresh provider
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
        trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]

        naas.library.otel.init_telemetry(service_name="test-svc")
        provider = trace.get_tracer_provider()
        assert provider.resource.attributes["service.name"] == "test-svc"

    def test_span_creates_span(self, _enable_otel) -> None:
        exporter = _enable_otel
        from naas.library.otel import span

        with span("test.operation", attributes={"key": "val"}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.operation"
        assert spans[0].attributes["key"] == "val"

    def test_span_records_exception(self, _enable_otel) -> None:
        exporter = _enable_otel
        from naas.library.otel import span

        with pytest.raises(RuntimeError):
            with span("failing.op"):
                raise RuntimeError("test error")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.is_ok is False
        events = spans[0].events
        assert any(e.name == "exception" for e in events)

    def test_inject_and_extract_traceparent(self, _enable_otel) -> None:
        from naas.library.otel import extract_context, inject_traceparent, span

        with span("parent.span"):
            meta: dict = {}
            inject_traceparent(meta)

        assert "traceparent" in meta
        assert meta["traceparent"].startswith("00-")

        # Extract should return a valid context
        ctx = extract_context(meta)
        assert ctx is not None

    def test_child_span_links_to_parent_via_traceparent(self, _enable_otel) -> None:
        exporter = _enable_otel
        from naas.library.otel import extract_context, inject_traceparent, span

        # Simulate API side: create parent span and inject traceparent
        with span("api.enqueue"):
            meta: dict = {}
            inject_traceparent(meta)

        # Simulate worker side: extract context and create child span
        parent_ctx = extract_context(meta)
        with span("worker.execute", parent_context=parent_ctx):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        api_span = next(s for s in spans if s.name == "api.enqueue")
        worker_span = next(s for s in spans if s.name == "worker.execute")

        # Same trace ID = linked
        assert api_span.context.trace_id == worker_span.context.trace_id
        # Worker is child of API
        assert worker_span.parent.span_id == api_span.context.span_id
