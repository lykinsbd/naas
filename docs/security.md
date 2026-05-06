# Security best practices

Guidelines for securing your NAAS deployment.

## Contents

- [Transport Security](#transport-security)
- [Authentication](#authentication)
- [Network Security](#network-security)
- [Credential Management](#credential-management)
- [Access Control](#access-control)
- [Monitoring and Auditing](#monitoring-and-auditing)
- [Container Security](#container-security)

## Transport security

### Always use HTTPS

NAAS transmits credentials to network devices. **Never** use HTTP in production.

**Default**: NAAS generates a self-signed certificate at startup if no certificate is provided.

**Production**: Supply a valid TLS certificate:

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

### TLS Configuration

TLS is handled by Gunicorn directly — no reverse proxy required. The cipher suite and minimum TLS version are hardcoded to secure defaults:

- **Minimum version**: TLS 1.2
- **Ciphers**: `HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!3DES:!MD5:!PSK`

For custom cipher configuration, use a reverse proxy (see [Reverse Proxy](#reverse-proxy) below).

### Certificate Rotation

Rotate certificates before expiration:

```bash
# Check certificate expiration
openssl x509 -in cert.pem -noout -enddate
```

=== "Docker Compose"

    ```bash
    export NAAS_CERT=$(cat new-cert.pem)
    export NAAS_KEY=$(cat new-key.pem)
    export NAAS_CA_BUNDLE=$(cat new-bundle.pem)
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set secrets.tlsCert="$(cat new-cert.pem)" \
      --set secrets.tlsKey="$(cat new-key.pem)" \
      --set secrets.tlsCaBundle="$(cat new-bundle.pem)"
    ```

    Or with cert-manager, rotation is automatic.

## Authentication

### Basic Authentication

NAAS uses HTTP Basic Authentication. Credentials are passed through to network devices.

**Important**:

- Credentials are **not** stored by NAAS
- Credentials are transmitted to the target device
- Always use HTTPS to protect credentials in transit

### Device Credentials

**Best Practices**:

1. **Use dedicated service accounts** for automation
2. **Rotate credentials regularly**
3. **Use least privilege** - only grant necessary permissions
4. **Monitor authentication failures** - detect brute force attempts

### Enable Password

For devices requiring enable mode:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "enable": "enable_password",
  "commands": ["show running-config"]
}
```

**Note**: Enable passwords are also transmitted securely over HTTPS.

## Network Security

### Firewall Rules

Restrict access to NAAS:

```bash
# Allow only from specific networks
sudo ufw allow from 10.0.0.0/8 to any port 8443
sudo ufw deny 8443

# Or using iptables
sudo iptables -A INPUT -p tcp -s 10.0.0.0/8 --dport 8443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8443 -j DROP
```

### Network Segmentation

Deploy NAAS in a management network:

```text
[Automation Tools] --> [NAAS] --> [Network Devices]
     10.0.1.0/24      10.0.2.0/24    10.0.3.0/24
```

**Benefits**:

- Limit blast radius
- Easier to audit and monitor
- Centralized access control

### Reverse Proxy

Use a reverse proxy for additional security:

```nginx
# nginx.conf
upstream naas {
    server localhost:8443;
}

server {
    listen 443 ssl http2;
    server_name naas.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=naas:10m rate=10r/s;
    limit_req zone=naas burst=20;

    location / {
        proxy_pass https://naas;
        proxy_ssl_verify off;

        # Pass through auth headers
        proxy_set_header Authorization $http_authorization;
        proxy_pass_header Authorization;
    }
}
```

## Credential Management

### Avoid Hardcoding Credentials

**Bad**:

```python
# Don't do this!
response = requests.post(
    "https://naas.example.com/v2/send-command",
    auth=("admin", "password123"),  # Hardcoded!
    json=payload
)
```

**Good**:

```python
import os
from requests.auth import HTTPBasicAuth

# Use environment variables
username = os.environ["DEVICE_USERNAME"]
password = os.environ["DEVICE_PASSWORD"]

response = requests.post(
    "https://naas.example.com/v2/send-command",
    auth=HTTPBasicAuth(username, password),
    json=payload
)
```

### Use Secrets Management

Integrate with secrets management systems:

```python
# Using HashiCorp Vault
import hvac

client = hvac.Client(url='https://vault.example.com')
secret = client.secrets.kv.v2.read_secret_version(path='network/devices')

username = secret['data']['data']['username']
password = secret['data']['data']['password']
```

### Credential Rotation

Implement automated credential rotation:

1. Generate new credentials
2. Update on all devices
3. Update in secrets management
4. Verify NAAS can authenticate
5. Revoke old credentials

## Access Control

### Redis Security

Secure Redis with authentication:

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

### Container Isolation

Run with minimal privileges:

=== "Docker Compose"

    ```yaml
    # docker-compose.override.yml
    services:
      api:
        security_opt:
          - no-new-privileges:true
        read_only: true
        tmpfs:
          - /tmp
        user: "1000:1000"
    ```

=== "Kubernetes"

    The Helm chart applies these by default: non-root UID 1000, all capabilities dropped, read-only root filesystem. No additional configuration needed.

### Rate Limiting

NAAS includes a built-in per-caller sliding window rate limiter backed by Redis sorted sets. It applies to all submission endpoints (`/v2/send-command`, `/v2/send-config`, `/v2/send-command-structured`).

**Two tiers:**

- **Per-caller:** Limits total submissions across all devices for a given identity
- **Per-caller-per-device:** Limits submissions to a single device from a given identity

When a limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

**Configuration (environment variables):**

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_PER_CALLER` | `1000` | Max requests per caller per window |
| `RATE_LIMIT_PER_CALLER_DEVICE` | `20` | Max requests per caller per device per window |
| `RATE_LIMIT_WINDOW` | `60` | Sliding window size in seconds |
| `RATE_LIMIT_EXEMPT_ROLES` | `admin` | Comma-separated roles exempt from limits |

**Response headers** (included on every submission response):

- `X-RateLimit-Limit` — the applicable limit
- `X-RateLimit-Remaining` — requests remaining in the window
- `X-RateLimit-Reset` — Unix timestamp when the window resets

**429 response body:**

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

Basic auth users are implicitly exempt (treated as admin). API key users are subject to limits based on their role.

You can also add external rate limiting via a reverse proxy (see the nginx example above).

## Monitoring and Auditing

### Structured Audit Events

NAAS emits structured JSON audit events at INFO level via the `NAAS` logger. Each
event includes an `event_type` field for filtering.

#### Authentication Events

| Event | Fields | Description |
| --- | --- | --- |
| `auth.success` | `method`, `identity` | Successful authentication (Basic or Bearer) |
| `auth.failure` | `method`, `reason` | Failed authentication attempt |

#### Authorization Events

| Event | Fields | Description |
| --- | --- | --- |
| `auth.context_denied` | `identity`, `context`, `allowed_contexts` | Context authorization failure |
| `auth.rbac_denied` | `identity`, `role`, `required_role`, `endpoint` | Insufficient role |

#### API Key Management Events

| Event | Fields | Description |
| --- | --- | --- |
| `apikey.created` | `key_id`, `role`, `contexts`, `created_by` | New API key created |
| `apikey.revoked` | `key_id`, `revoked_by` | API key revoked |

#### Job Lifecycle Events

| Event | Fields | Description |
| --- | --- | --- |
| `job.submitted` | `host`, `platform`, `port`, `command_count`, `user_hash`, `request_id` | Job enqueued |
| `job.completed` | `request_id`, `status`, `duration_ms` | Job finished |
| `job.cancelled` | `request_id`, `cancelled_by_hash` | Job cancelled |
| `job.orphaned` | `request_id`, `worker_name` | Orphaned job reaped |

#### Device Events

| Event | Fields | Description |
| --- | --- | --- |
| `device.locked_out` | `host`, `failure_count` | Device locked after repeated failures |
| `circuit.opened` | `host` | Circuit breaker opened |
| `circuit.closed` | `host` | Circuit breaker closed |

**Data privacy**: Audit events never contain passwords, command output, or API key
tokens. Only usernames, key IDs, and operational metadata are logged.

### Filtering Audit Events

Audit events are mixed with operational logs in the JSON output stream. Filter on
the `event_type` field:

=== "Docker Compose"

    ```bash
    docker compose logs api | jq 'select(.event_type)'
    docker compose logs api | jq 'select(.event_type == "auth.failure")'
    docker compose logs api | jq 'select(.event_type | startswith("auth."))'
    ```

=== "Kubernetes"

    ```bash
    kubectl -n naas logs deploy/naas-api | jq 'select(.event_type)'
    kubectl -n naas logs deploy/naas-api | jq 'select(.event_type == "auth.failure")'
    kubectl -n naas logs deploy/naas-api | jq 'select(.event_type | startswith("auth."))'
    ```

### SIEM Integration

Ship structured JSON logs to your SIEM using any log shipper (Fluentd, Vector,
Filebeat). Filter on `event_type` to route audit events to a dedicated index.

### Tamper-Evident Logging

For compliance, ship logs to an append-only store:

- **AWS**: CloudWatch Logs with retention policy
- **S3**: With Object Lock enabled
- **Syslog**: Forward to a hardened syslog server

### Recommended Alerts

| Event | Alert condition | Indicates |
| --- | --- | --- |
| `auth.failure` | >10 in 5 minutes | Brute force attempt |
| `auth.rbac_denied` | Any occurrence | Privilege escalation attempt |
| `apikey.created` | Any occurrence | New API key (verify expected) |
| `device.locked_out` | Any occurrence | Device under attack or misconfigured |

### Log Aggregation

Send logs to centralized logging:

=== "Docker Compose"

    ```yaml
    # docker-compose.override.yml
    services:
      api:
        logging:
          driver: "syslog"
          options:
            syslog-address: "tcp://logserver.example.com:514"
            tag: "naas-api"
      worker:
        logging:
          driver: "syslog"
          options:
            syslog-address: "tcp://logserver.example.com:514"
            tag: "naas-worker"
    ```

=== "Kubernetes"

    Use a log shipper DaemonSet (Fluentd, Vector, Filebeat) to collect pod logs from `/var/log/containers/`. NAAS emits structured JSON, so no parsing is needed — route directly to your SIEM or log backend.

### Monitor Authentication Failures

Set up alerts for `auth.failure` events (see [Recommended Alerts](#recommended-alerts) above).

## Container Security

### Keep Images Updated

Regularly update NAAS and dependencies:

=== "Docker Compose"

    ```bash
    docker compose pull
    docker compose up -d
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas --set image.tag=2.1.0
    ```

### Scan for Vulnerabilities

Use container scanning tools:

```bash
# Using Trivy
trivy image ghcr.io/lykinsbd/naas:latest

# Using Docker Scout
docker scout cves ghcr.io/lykinsbd/naas:latest
```

### Resource Limits

Prevent resource exhaustion:

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
            reservations:
              cpus: '0.5'
              memory: 256M
      worker:
        deploy:
          resources:
            limits:
              cpus: '2'
              memory: 1G
            reservations:
              cpus: '1'
              memory: 512M
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas \
      --set api.resources.limits.cpu=1000m \
      --set api.resources.limits.memory=512Mi \
      --set worker.resources.limits.cpu=2000m \
      --set worker.resources.limits.memory=1Gi
    ```

### Read-Only Filesystem

Run containers with read-only root filesystem:

```yaml
# docker-compose.override.yml
services:
  api:
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

## Security Checklist

Before deploying to production:

- [ ] Use valid TLS certificates (not self-signed)
- [ ] Configure firewall rules
- [ ] Use strong Redis password
- [ ] Enable production logging
- [ ] Set up log aggregation
- [ ] Configure rate limiting
- [ ] Implement network segmentation
- [ ] Use secrets management for credentials
- [ ] Set resource limits on containers
- [ ] Enable container security options
- [ ] Set up monitoring and alerting
- [ ] Document incident response procedures
- [ ] Plan credential rotation schedule
- [ ] Review and update regularly

## Compliance Considerations

### PCI DSS

If handling payment card data:

- Use TLS 1.2 or higher
- Implement strong access controls
- Log all access to network devices
- Encrypt credentials at rest and in transit

### SOC 2

For SOC 2 compliance:

- Maintain audit logs
- Implement access controls
- Monitor for security events
- Document security procedures

### HIPAA

For healthcare environments:

- Encrypt all data in transit
- Implement access controls
- Maintain audit trails
- Use secure credential management

## Incident Response

### Security Incident Procedure

1. **Detect**: Monitor logs for suspicious activity
2. **Contain**: Isolate affected systems
3. **Investigate**: Review logs and audit trail
4. **Remediate**: Rotate credentials, patch vulnerabilities
5. **Document**: Record incident details and response

### Emergency Shutdown

=== "Docker Compose"

    ```bash
    # Stop all NAAS services immediately
    docker compose down

    # Clear Redis data if compromised
    docker compose down -v
    ```

=== "Kubernetes (Helm)"

    ```bash
    # Stop all NAAS services
    helm uninstall naas

    # Or delete the namespace entirely (including PVCs)
    kubectl delete namespace naas
    ```

## Next steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [API Usage Examples](api-usage.md) - Learn the API
- [Quick Start Guide](quickstart.md) - Get started with NAAS
