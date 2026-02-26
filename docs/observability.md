# Observability

NAAS v1.1 ships structured logging and request tracing out of the box.

## Structured JSON Logging

All log output is JSON. Each line includes:

| Field | Description |
|---|---|
| `timestamp` | ISO 8601 timestamp |
| `level` | Log level (`INFO`, `DEBUG`, `WARNING`, `ERROR`) |
| `logger` | Logger name (e.g. `NAAS`) |
| `message` | Log message |

Example log line:

```json
{"timestamp": "2026-02-26T17:00:00.000Z", "level": "INFO", "logger": "NAAS", "message": "abc123: admin is issuing 2 command(s) to 192.168.1.1:22"}
```

This format is directly ingestible by ELK, Splunk, CloudWatch Logs, Datadog, and similar tools.

### Log Level

Set via `LOG_LEVEL` environment variable (default: `INFO`). Use `DEBUG` for verbose output including per-command device interaction.

```bash
LOG_LEVEL=DEBUG docker compose up -d
```

## Correlation ID Tracing

Every API request is assigned a UUID correlation ID (`request_id`). This ID:

- Is returned as `X-Request-ID` in the response header
- Is used as the RQ job ID
- Appears as the first field in all worker log lines for that job

This enables end-to-end tracing of a single request across API and worker logs.

### Supplying your own ID

Pass `X-Request-ID` in the request to use your own correlation ID (must be a valid UUID v4):

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"ip": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

If omitted, NAAS generates one automatically.

### Tracing a request through logs

```bash
# Find all log lines for a specific job
docker compose logs worker | grep "550e8400-e29b-41d4-a716-446655440000"
```

## Health Check

`GET /healthcheck` performs a live Redis ping and reports component status:

```json
{
  "status": "healthy",
  "version": "1.1.0",
  "uptime_seconds": 3600,
  "components": {
    "redis": { "status": "healthy" },
    "queue": { "status": "healthy", "depth": 4 }
  }
}
```

`status` is `"healthy"` when all components are up, `"degraded"` when Redis is unreachable. Use this endpoint for load balancer health checks and uptime monitoring.
