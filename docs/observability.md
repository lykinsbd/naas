# Observability

NAAS provides structured logging, request tracing, and Prometheus metrics for monitoring and troubleshooting.

## Contents

- [Structured JSON Logging](#structured-json-logging)
- [Correlation ID Tracing](#correlation-id-tracing)
- [Prometheus Metrics](#prometheus-metrics)
- [Audit Events](#audit-events)

## Structured JSON Logging

All log output is JSON. Each line includes:

| Field | Description |
| --- | --- |
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
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
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

## Prometheus Metrics

NAAS exposes Prometheus-compatible metrics at the `/metrics` endpoint for monitoring performance and health.

### Accessing Metrics

```bash
curl -k https://localhost:8443/metrics
```

**Note:** The `/metrics` endpoint does not require authentication.

### Available Metrics

#### Request Metrics

- `naas_http_requests_total{method, endpoint, status}` - Total HTTP requests by method, endpoint, and status code
- `naas_http_request_duration_seconds{method, endpoint}` - Request latency histogram

#### Queue Metrics

- `naas_queue_depth` - Current number of jobs in the Redis queue
- `naas_queue_jobs_total{status}` - Total jobs by status (queued, started, finished, failed)

#### Worker Metrics

- `naas_workers_active` - Number of active RQ workers
- `naas_workers_busy` - Number of workers currently processing jobs

#### Job Metrics

- `naas_jobs_duration_seconds{platform}` - Job execution time histogram by platform
- `naas_jobs_total{platform, status}` - Total jobs by platform and status

### Grafana Dashboard

Example Grafana queries:

**Request rate:**

```promql
rate(naas_http_requests_total[5m])
```

**P95 latency:**

```promql
histogram_quantile(0.95, rate(naas_http_request_duration_seconds_bucket[5m]))
```

**Queue depth over time:**

```promql
naas_queue_depth
```

**Worker utilization:**

```promql
naas_workers_busy / naas_workers_active
```

### Integration with Monitoring Systems

#### Prometheus

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'naas'
    static_configs:
      - targets: ['naas-api:8443']
    scheme: https
    tls_config:
      insecure_skip_verify: true
```

#### CloudWatch

Use [CloudWatch Agent with Prometheus support](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-PrometheusEC2.html) to scrape `/metrics` and send to CloudWatch.

#### Datadog

Use [Datadog Agent OpenMetrics integration](https://docs.datadoghq.com/integrations/openmetrics/) to collect metrics.

## Audit Events

NAAS emits structured audit events for job lifecycle tracking and security monitoring.

### Event Types

- `job.submitted` - Job submitted to queue
- `job.started` - Worker began processing job
- `job.completed` - Job finished (success or failure)
- `device.failure` - Device connection or authentication failure

### Event Format

Events are logged as JSON with these fields:

```json
{
  "timestamp": "2026-03-04T19:00:00.000Z",
  "level": "INFO",
  "logger": "naas.audit",
  "event_type": "job.completed",
  "request_id": "abc-123",
  "username": "admin",
  "device_ip": "192.168.1.1",
  "platform": "cisco_ios",
  "status": "finished",
  "duration_ms": 1234
}
```

### Consuming Audit Events

Filter logs by `logger: "naas.audit"` to extract audit events:

**CloudWatch Logs Insights:**

```text
fields @timestamp, event_type, username, device_ip, status
| filter logger = "naas.audit"
| sort @timestamp desc
```

**Splunk:**

```json
index=naas logger="naas.audit" | table _time event_type username device_ip status
```

**ELK:**

```json
{
  "query": {
    "term": { "logger": "naas.audit" }
  }
}
```

### Use Cases

- **Security auditing**: Track who accessed which devices
- **Compliance**: Maintain audit trail of network changes
- **Troubleshooting**: Correlate failures with device/user patterns
- **Capacity planning**: Analyze job duration and volume trends

## Job Reaper

The job reaper is a background thread that runs in each worker process. It detects jobs that are stuck in the `started` state because their worker died (OOM kill, node failure, SIGKILL) and moves them to the `failed` state.

### Why It Matters

Without the reaper, a dead worker leaves its in-flight jobs stuck in `StartedJobRegistry` until RQ's job timeout expires (up to the full `JOB_TIMEOUT`). During this window:

- The job appears to be running but will never complete
- The dedup key blocks re-submission of the same job
- Clients polling for results see `status: started` indefinitely

The reaper detects this within `WORKER_STALE_THRESHOLD` seconds (default 120s) and moves the job to `failed`, clearing the dedup key so the job can be re-submitted.

### Distributed Lock

All workers run the reaper thread, but only one executes per cycle. The reaper acquires a Redis lock (`naas:reaper:lock`) before scanning. If another reaper holds the lock, the current one skips that cycle. The lock TTL equals `JOB_REAPER_INTERVAL`, so it self-heals if the lock holder dies.

### Audit Event

When a job is reaped, a `job.orphaned` audit event is emitted:

```json
{
  "event": "job.orphaned",
  "job_id": "abc-123",
  "worker_name": "naas_worker_1"
}
```

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `JOB_REAPER_ENABLED` | `true` | Enable orphaned job detection |
| `JOB_REAPER_INTERVAL` | `60` | Seconds between reaper scans |
| `WORKER_STALE_THRESHOLD` | `120` | Seconds since last heartbeat before worker considered dead |
