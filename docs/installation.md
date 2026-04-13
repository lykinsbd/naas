# Installation

## Docker Compose (Recommended)

The easiest way to run NAAS is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Start services
docker compose up -d

# Verify it's running
curl -k https://localhost:8443/healthcheck
```

## Manual Installation

### Prerequisites

- Python 3.11+
- Redis 6.0+
- uv (Python package manager)

### Steps

```bash
# Clone repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Install dependencies
uv sync

# Set environment variables
export REDIS_HOST=localhost
export REDIS_PORT=6379
export NAAS_USERNAME=admin
export NAAS_PASSWORD=password

# Start Redis
redis-server

# Start API server
uv run gunicorn -c gunicorn.py naas.app:app

# Start worker (in another terminal)
uv run python worker.py
```

## Configuration

See [Security](security.md) for production configuration options.

### OpenTelemetry tracing

NAAS supports optional distributed tracing via [OpenTelemetry](https://opentelemetry.io/).
Traces follow the full request lifecycle: API request → RQ queue → worker → SSH device.

Install the optional dependencies:

```bash
pip install naas[otel]
```

Configure via environment variables:

| Variable                      | Default | Description                                                 |
| ----------------------------- | ------- | ----------------------------------------------------------- |
| `OTEL_ENABLED`                | `false` | Enable OpenTelemetry instrumentation                        |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (none)  | OTLP collector endpoint (e.g. `http://otel-collector:4317`) |

When disabled (default), tracing adds zero overhead: no OTel packages are imported and all
instrumentation functions are no-ops.

When enabled, NAAS creates the following spans:

- `naas.worker.execute`: Worker picks up and runs a job
- `naas.netmiko.connect`: SSH connection establishment
- `naas.netmiko.send_command`: Per-command execution
- `naas.netmiko.send_config`: Configuration push

Flask HTTP spans are auto-instrumented. Trace context propagates through the RQ queue
via W3C `traceparent` in job metadata, linking API and worker spans into a single trace.

See [ADR 0008](adr/0008-opentelemetry-instrumentation-strategy.md) for design decisions.
