# Environment Variables Reference

All NAAS configuration is driven by environment variables. Set these in `docker-compose.yml`, a `.env` file, or your deployment platform's secrets manager.

## Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | `mah_redis_pw` | Redis password |

## Application

| Variable | Default | Description |
|---|---|---|
| `APP_ENVIRONMENT` | `production` | Set to `dev` for debug logging and relaxed settings |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Overridden to `DEBUG` when `APP_ENVIRONMENT=dev` |

## Jobs

| Variable | Default | Description |
|---|---|---|
| `JOB_TTL_SUCCESS` | `86400` | Seconds to retain successful job results in Redis (default: 24h) |
| `JOB_TTL_FAILED` | `604800` | Seconds to retain failed job results in Redis (default: 7 days) |

## Worker

| Variable | Default | Description |
|---|---|---|
| `SHUTDOWN_TIMEOUT` | `60` | Seconds to wait for an in-flight job to complete before force-exiting on SIGTERM |

## Circuit Breaker

| Variable | Default | Description |
|---|---|---|
| `CIRCUIT_BREAKER_ENABLED` | `true` | Set to `false` to disable the circuit breaker entirely |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Number of consecutive failures before a device's circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT` | `300` | Seconds before a tripped circuit attempts recovery (half-open state) |

## Example docker-compose.yml

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

  worker:
    environment:
      - REDIS_HOST=redis
      - REDIS_PASSWORD=your-secure-password
      - SHUTDOWN_TIMEOUT=60
      - CIRCUIT_BREAKER_THRESHOLD=5
      - CIRCUIT_BREAKER_TIMEOUT=300
```
