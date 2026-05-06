# Security

NAAS transmits SSH credentials to network devices. This page covers how to secure the deployment itself.

## TLS

NAAS listens on HTTPS only. Gunicorn handles TLS directly — no reverse proxy required.

**Default behavior:** Generates a self-signed certificate at startup if none is provided.

**Production:** Supply a valid certificate:

=== "Docker Compose"

    ```bash
    export NAAS_CERT=$(cat /path/to/fullchain.pem)
    export NAAS_KEY=$(cat /path/to/privkey.pem)
    export NAAS_CA_BUNDLE=$(cat /path/to/chain.pem)
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set secrets.tlsCert="$(cat fullchain.pem)" \
      --set secrets.tlsKey="$(cat privkey.pem)" \
      --set secrets.tlsCaBundle="$(cat chain.pem)"
    ```

    With cert-manager, create a `Certificate` resource and reference the resulting secret via `secrets.existingSecret`.

**TLS settings** (hardcoded, not configurable):

- Minimum version: TLS 1.2
- Ciphers: `HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!3DES:!MD5:!PSK`

To customize ciphers, terminate TLS at a reverse proxy instead.

### Certificate Rotation

```bash
openssl x509 -in cert.pem -noout -enddate
```

=== "Docker Compose"

    ```bash
    export NAAS_CERT=$(cat new-cert.pem)
    export NAAS_KEY=$(cat new-key.pem)
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set secrets.tlsCert="$(cat new-cert.pem)" \
      --set secrets.tlsKey="$(cat new-key.pem)"
    ```

## Authentication

NAAS supports two authentication methods:

- **HTTP Basic Auth** — Credentials are passed through to the target device as SSH credentials. NAAS does not store them.
- **JWT API keys** — Created via `/v2/api-keys`. Scoped by role and context. Used for automation and service-to-service access.

### RBAC

| Role | Can do |
|------|--------|
| `admin` | Everything, including API key management |
| `operator` | Submit jobs, view results |
| `viewer` | View job status and results only |

API keys carry a `role` and optional `contexts` claim. Requests to endpoints above the key's role return `403`.

### Device Credentials

NAAS is a pass-through — it connects to devices using whatever credentials the caller provides. Use dedicated service accounts with least privilege on your devices. Rotate them on your own schedule.

For devices requiring enable mode:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "enable": "enable_password",
  "commands": ["show running-config"]
}
```

## Redis

Redis holds the job queue, results, circuit breaker state, and rate limit counters. Secure it:

=== "Docker Compose"

    ```bash
    export REDIS_PASSWORD=$(openssl rand -base64 32)
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set secrets.redisPassword=$(openssl rand -base64 32)
    ```

    Or reference an existing secret: `--set secrets.existingSecret=my-naas-secrets`

For production, use a managed Redis (ElastiCache, Redis Cloud, etc.) with encryption in transit and at rest. The bundled Redis is single-replica with no persistence.

## Rate Limiting

Built-in per-caller sliding window rate limiter on all submission endpoints.

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable |
| `RATE_LIMIT_PER_CALLER` | `1000` | Max requests per caller per window |
| `RATE_LIMIT_PER_CALLER_DEVICE` | `20` | Max requests per caller per device per window |
| `RATE_LIMIT_WINDOW` | `60` | Window size in seconds |
| `RATE_LIMIT_EXEMPT_ROLES` | `admin` | Roles exempt from limits |

When exceeded, returns `429 Too Many Requests` with `Retry-After` header. Basic auth users are exempt (treated as admin role).

Response headers on every submission:

- `X-RateLimit-Limit` — applicable limit
- `X-RateLimit-Remaining` — requests left in window
- `X-RateLimit-Reset` — Unix timestamp when window resets

## Container Security

The Helm chart and default `docker-compose.yml` apply these by default:

- Non-root user (UID 1000)
- All Linux capabilities dropped (API retains `NET_BIND_SERVICE` for port 443)
- Read-only root filesystem (`/tmp` writable via tmpfs)

### Resource Limits

=== "Docker Compose"

    ```yaml
    # docker-compose.override.yml
    services:
      api:
        deploy:
          resources:
            limits:
              cpus: '1'
              memory: 512M
      worker:
        deploy:
          resources:
            limits:
              cpus: '2'
              memory: 1G
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set api.resources.limits.cpu=1000m \
      --set api.resources.limits.memory=512Mi \
      --set worker.resources.limits.cpu=2000m \
      --set worker.resources.limits.memory=1Gi
    ```

### Image Updates

=== "Docker Compose"

    ```bash
    docker compose pull
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas --set image.tag=2.1.0
    ```

Scan images with `trivy image ghcr.io/lykinsbd/naas:latest` or Docker Scout.

## Audit Events

NAAS emits structured JSON audit events via the `NAAS` logger. Each event has an `event_type` field.

### Event Reference

| Event | Key Fields | Meaning |
|-------|-----------|---------|
| `auth.success` | `method`, `identity` | Successful authentication |
| `auth.failure` | `method`, `reason` | Failed authentication attempt |
| `auth.context_denied` | `identity`, `context`, `allowed_contexts` | Context authorization failure |
| `auth.rbac_denied` | `identity`, `role`, `required_role`, `endpoint` | Insufficient role |
| `apikey.created` | `key_id`, `role`, `contexts`, `created_by` | New API key created |
| `apikey.revoked` | `key_id`, `revoked_by` | API key revoked |
| `job.submitted` | `host`, `platform`, `command_count`, `request_id` | Job enqueued |
| `job.completed` | `request_id`, `status`, `duration_ms` | Job finished |
| `job.cancelled` | `request_id`, `cancelled_by_hash` | Job cancelled |
| `job.orphaned` | `request_id`, `worker_name` | Orphaned job reaped |
| `device.locked_out` | `host`, `failure_count` | Device locked after repeated failures |
| `circuit.opened` | `host` | Circuit breaker tripped |
| `circuit.closed` | `host` | Circuit breaker recovered |

Audit events never contain passwords, command output, or API key tokens.

### Filtering

=== "Docker Compose"

    ```bash
    docker compose logs api | jq 'select(.event_type)'
    docker compose logs api | jq 'select(.event_type | startswith("auth."))'
    ```

=== "Kubernetes"

    ```bash
    kubectl -n naas logs deploy/naas-api | jq 'select(.event_type)'
    ```

Ship to your SIEM via any log shipper (Fluentd, Vector, Filebeat). Filter on `event_type` to route audit events to a dedicated index.

### Recommended Alerts

| Event | Condition | Indicates |
|-------|-----------|-----------|
| `auth.failure` | >10 in 5 minutes | Brute force attempt |
| `auth.rbac_denied` | Any occurrence | Privilege escalation attempt |
| `apikey.created` | Any occurrence | New API key — verify expected |
| `device.locked_out` | Any occurrence | Device under attack or misconfigured credentials |

## Reverse Proxy (Optional)

If you need custom TLS ciphers, additional rate limiting, or security headers beyond what NAAS provides:

```nginx
server {
    listen 443 ssl http2;
    server_name naas.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass https://naas;
        proxy_ssl_verify off;
        proxy_set_header Authorization $http_authorization;
    }
}
```

## Emergency Shutdown

=== "Docker Compose"

    ```bash
    docker compose down        # Stop services
    docker compose down -v     # Stop and wipe Redis data
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm uninstall naas              # Remove release
    kubectl delete namespace naas    # Remove everything including PVCs
    ```

## Pre-Production Checklist

- [ ] Valid TLS certificate (not self-signed)
- [ ] Strong Redis password
- [ ] Rate limiting configured
- [ ] Resource limits set
- [ ] Log aggregation configured
- [ ] Alerts on `auth.failure` and `device.locked_out`
- [ ] Network access restricted to authorized callers
- [ ] Container images scanned for vulnerabilities
