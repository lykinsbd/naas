# Environment Variables Reference

All NAAS configuration is driven by environment variables. Set these in your Helm `values.yaml` (under `config:`), `docker-compose.yml`, a `.env` file, or your deployment platform's secrets manager.

## Redis

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | `mah_redis_pw` | Redis password |

## Application

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `production` | Set to `dev` for debug logging and relaxed settings |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Overridden to `DEBUG` when `APP_ENVIRONMENT=dev` |
| `GUNICORN_WORKERS` | `8` | Number of gunicorn worker processes. Reduce (e.g. `2`) in resource-constrained environments |

## Jobs

| Variable | Default | Description |
| --- | --- | --- |
| `JOB_TTL_SUCCESS` | `86400` | Seconds to retain successful job results in Redis (default: 24h) |
| `JOB_TTL_FAILED` | `604800` | Seconds to retain failed job results in Redis (default: 7 days) |
| `FAILED_JOB_MAX_RETAIN` | `500` | Maximum number of failed jobs to retain in the dead letter queue |

## Worker

| Variable | Default | Description |
| --- | --- | --- |
| `SHUTDOWN_TIMEOUT` | `60` | Seconds to wait for an in-flight job to complete before force-exiting on SIGTERM |

## Circuit Breaker

| Variable | Default | Description |
| --- | --- | --- |
| `CIRCUIT_BREAKER_ENABLED` | `true` | Set to `false` to disable the circuit breaker entirely |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Number of consecutive failures before a device's circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT` | `300` | Seconds before a tripped circuit attempts recovery (half-open state) |

## Connection Pool

| Variable | Default | Description |
| --- | --- | --- |
| `CONNECTION_POOL_ENABLED` | `true` | Enable persistent SSH connection pooling |
| `CONNECTION_POOL_MAX_SIZE` | `10` | Maximum connections per worker |
| `CONNECTION_POOL_TTL` | `300` | Idle timeout in seconds before closing connections |
| `CONNECTION_POOL_KEEPALIVE` | `30` | SSH keepalive interval in seconds |
| `CONNECTION_POOL_EXCLUDE` | `` | Comma-separated IPs or device_types to exclude from pooling (e.g. `192.168.1.1,cisco_ios_old`) |

## Context Routing

| Variable | Default | Description |
| --- | --- | --- |
| `NAAS_CONTEXTS` | `default` | Comma-separated list of valid context names (e.g. `default,corp,oob-dc1,hk-prod`) |
| `WORKER_CONTEXTS` | `default` | Comma-separated contexts this worker serves (e.g. `oob-dc1,oob-dc2`) |
| `MAX_QUEUE_DEPTH` | `0` | Max queued jobs before returning 503 (0 = disabled) |
| `IDEMPOTENCY_TTL` | `86400` | Seconds to remember idempotency keys (24h) |
| `JOB_DEDUP_ENABLED` | `true` | Enable server-side job deduplication (opt-out) |
| `WEBHOOK_ALLOW_HTTP` | `false` | Allow HTTP webhook URLs (HTTPS only by default; enable for testing) |
| `JOB_REAPER_ENABLED` | `true` | Enable orphaned job detection (opt-out) |
| `JOB_REAPER_INTERVAL` | `60` | Seconds between reaper scans |
| `WORKER_STALE_THRESHOLD` | `120` | Seconds since last heartbeat before worker considered dead |

## Rate Limiting

| Variable | Default | Description |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable built-in rate limiting |
| `RATE_LIMIT_PER_CALLER` | `1000` | Max submissions per caller per window |
| `RATE_LIMIT_PER_CALLER_DEVICE` | `20` | Max submissions per caller per device per window |
| `RATE_LIMIT_WINDOW` | `60` | Sliding window size in seconds |
| `RATE_LIMIT_EXEMPT_ROLES` | `admin` | Comma-separated roles exempt from rate limits |

## OpenTelemetry

| Variable | Default | Description |
| --- | --- | --- |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry distributed tracing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC collector endpoint |

Requires the `otel` extra: `pip install naas[otel]`. Set on both API and worker processes.

## Configuration Examples

=== "Kubernetes (Helm values.yaml)"

    ```yaml
    config:
      LOG_LEVEL: "INFO"
      CIRCUIT_BREAKER_THRESHOLD: "5"
      CIRCUIT_BREAKER_TIMEOUT: "300"
      RATE_LIMIT_PER_CALLER: "1000"
      RATE_LIMIT_PER_CALLER_DEVICE: "20"
      OTEL_ENABLED: "true"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4317"

    secrets:
      redisPassword: "your-secure-password"

    worker:
      replicas: 4
    ```

    All `config.*` values are injected as a ConfigMap. Secrets are stored in a Kubernetes Secret.

=== "Docker Compose"

    ```yaml
    services:
      api:
        environment:
          - REDIS_HOST=redis
          - REDIS_PASSWORD=your-secure-password
          - LOG_LEVEL=INFO
          - JOB_TTL_SUCCESS=86400
          - JOB_TTL_FAILED=604800
          - CIRCUIT_BREAKER_THRESHOLD=5
          - CIRCUIT_BREAKER_TIMEOUT=300
          - RATE_LIMIT_PER_CALLER=1000
          - RATE_LIMIT_PER_CALLER_DEVICE=20
          - OTEL_ENABLED=true
          - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

      worker:
        environment:
          - REDIS_HOST=redis
          - REDIS_PASSWORD=your-secure-password
          - SHUTDOWN_TIMEOUT=60
          - CIRCUIT_BREAKER_THRESHOLD=5
          - CIRCUIT_BREAKER_TIMEOUT=300
          - OTEL_ENABLED=true
          - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
    ```
