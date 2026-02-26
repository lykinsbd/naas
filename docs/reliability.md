# Reliability

NAAS v1.1 includes several mechanisms to protect against device failures, abuse, and data loss.

## Circuit Breaker

The circuit breaker prevents repeated connection attempts to a device that is known to be unreachable or misbehaving.

### How it works

1. Each connection failure to a device increments that device's failure counter
2. When failures reach `CIRCUIT_BREAKER_THRESHOLD` (default: 5), the circuit **opens**
3. While open, all jobs targeting that device fail immediately with an error — no connection is attempted
4. After `CIRCUIT_BREAKER_TIMEOUT` seconds (default: 300 / 5 minutes), the circuit enters **half-open** state
5. The next job attempt is allowed through; if it succeeds, the circuit closes. If it fails, it opens again

### What the caller sees

When a circuit is open, the job completes immediately with `status: failed` and an error message:

```json
{
  "status": "failed",
  "error": "Circuit breaker open for device 192.168.1.1 - too many recent failures"
}
```

### Configuration

| Variable | Default | Description |
|---|---|---|
| `CIRCUIT_BREAKER_ENABLED` | `true` | Disable entirely if needed |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT` | `300` | Seconds before recovery attempt |

Circuit breaker state is stored in Redis, so it is shared across all worker instances.

## Device Lockout

Device lockout is a separate, API-layer protection against credential-spray abuse — where multiple users submit jobs to the same device in rapid succession.

### How it works

- 10 connection failures to the same device IP within 10 minutes (across any user) triggers a lockout
- While locked out, new job submissions to that device return `403 Forbidden` immediately
- The lockout window slides — it expires 10 minutes after the last failure

### What the caller sees

```http
HTTP/1.1 403 Forbidden
```

### Relationship to circuit breaker

The circuit breaker and device lockout are complementary:

- **Circuit breaker** — protects workers from wasting time on unreachable devices
- **Device lockout** — protects the API from being used to spray credentials across a device

## Graceful Shutdown

Workers handle `SIGTERM` gracefully. When a shutdown signal is received:

1. The worker stops accepting new jobs
2. Any in-flight job is allowed to complete
3. If the job does not complete within `SHUTDOWN_TIMEOUT` seconds, the worker force-exits

This prevents job loss during container restarts, deployments, and scaling events.

| Variable | Default | Description |
|---|---|---|
| `SHUTDOWN_TIMEOUT` | `60` | Seconds to wait for in-flight job before force-exit |

## Job TTL

Job results are retained in Redis for a configurable period to prevent unbounded memory growth:

| Variable | Default | Description |
|---|---|---|
| `JOB_TTL_SUCCESS` | `86400` | Seconds to retain successful results (24h) |
| `JOB_TTL_FAILED` | `604800` | Seconds to retain failed results (7 days) |

Failed jobs are retained longer by default to aid post-incident investigation.
