# NAAS Load Tests

Performance testing for NAAS using [Locust](https://locust.io/).

## Quick start

```bash
# Start the load testing stack
docker compose -f tests/load/docker-compose.load.yml up -d --build --wait

# Run smoke test (30s, 10 users)
uv run locust -f tests/load/locustfile.py --headless \
  -u 10 -r 10 -t 30s \
  --host https://localhost:18443

# Run with web UI (open http://localhost:8089)
uv run locust -f tests/load/locustfile.py --host https://localhost:18443

# Tear down
docker compose -f tests/load/docker-compose.load.yml down -v
```

## Profiles

### Smoke (CI — every PR)

- 10 concurrent users, 30 seconds
- Pass criteria: error rate < 1%, all jobs complete
- Catches gross regressions (throughput collapse, error spikes)

### Full profile (CI — RC tags)

Ramp stages over 10 minutes:

| Stage | Users | Duration |
| ----- | ----- | -------- |
| Warm-up | 5 | 1 min |
| Ramp | 5 → 50 | 2 min |
| Sustained | 50 | 5 min |
| Spike | 100 | 1 min |
| Cool-down | 10 | 1 min |

Results are uploaded as CI artifacts and committed to `baselines/`.

## Test scenarios

| Task | Weight | Description |
| ---- | ------ | ----------- |
| `send_command_and_wait` | 3 | Submit job → poll until complete. Custom `JOB` metric tracks e2e time. |
| `list_jobs` | 1 | GET `/v2/jobs` — measures API responsiveness under load. |
| `healthcheck` | 1 | GET `/healthcheck` — baseline latency measurement. |

## Configuration

Environment variables for the Locust process:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `NAAS_LOAD_API_KEY` | *(empty)* | API key for Bearer auth (preferred) |
| `NAAS_LOAD_USERNAME` | `admin` | Username for basic auth (fallback) |
| `NAAS_LOAD_PASSWORD` | `admin` | Password for basic auth (fallback) |
| `NAAS_LOAD_DEVICE` | `cisshgo` | Target device hostname |
| `NAAS_LOAD_DEVICE_PORT` | `10022` | Target device SSH port |

## Stack configuration

The `docker-compose.load.yml` stack is tuned for load testing:

- **API:** 4 Gunicorn workers
- **Worker:** 10 RQ processes on the `default` queue
- **cisshgo:** 5 replicas (prevents SSH mock from bottlenecking)
- **Redis:** single instance

## Baselines

Historical results are stored in `baselines/` as JSON per release:

```json
{
  "version": "2.0.0",
  "date": "2026-04-10",
  "config": {"workers": 1, "processes": 10, "cisshgo_replicas": 5},
  "results": {
    "throughput_jobs_per_sec": 12.3,
    "p50_ms": 1200,
    "p95_ms": 3400,
    "p99_ms": 5100,
    "error_rate_pct": 0.0,
    "max_queue_depth": 15
  }
}
```

Compare across releases to spot trends (p95 creeping up, throughput dropping).

## Interpreting results

- **`send_command [e2e]`**: The key metric. This is the full job lifecycle time (submit → poll → result). p95 under 5s at 50 users is a good target.
- **`/v2/send-command [submit]`**: Job submission latency. Should stay under 100ms regardless of load.
- **`/v2/send-command/{id} [poll]`**: Individual poll request latency. Should stay under 50ms.
- **`/v2/jobs`**: List endpoint latency. Degrades as queue depth grows.
- **Error rate**: Should be 0% under normal load. Errors above 1% indicate saturation.
