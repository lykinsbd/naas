# Installation

## Recommended: Quick Start

The fastest way to get NAAS running is the [Quick Start guide](quickstart.md) — up and running in 5 minutes with Docker Compose.

## Production Deployment

For production environments, see the [Deployment Overview](deployment/index.md) to choose the right method:

- **[Kubernetes (Helm)](kubernetes.md)** — Recommended for production
- **[Docker Compose](deployment/docker-compose.md)** — Development and small deployments
- **[Manual](deployment/index.md#manual-installation)** — Custom environments

## Configuration

All deployment methods share the same environment variables. See [Environment Variables](deployment/environment-variables.md) for the full reference.

## OpenTelemetry Tracing

NAAS supports optional distributed tracing via [OpenTelemetry](https://opentelemetry.io/).
Traces follow the full request lifecycle: API request → RQ queue → worker → SSH device.

Install the optional dependencies:

```bash
pip install naas[otel]
```

| Variable | Default | Description |
| --- | --- | --- |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry instrumentation |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (none) | OTLP collector endpoint (e.g. `http://otel-collector:4317`) |

When disabled (default), tracing adds zero overhead. See [Observability](observability.md) for full details and [ADR 0008](adr/0008-opentelemetry-instrumentation-strategy.md) for design decisions.
