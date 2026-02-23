# Security best practices

Guidelines for securing your NAAS deployment.

## Table of contents

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

**Default**: NAAS uses HTTPS with self-signed certificates.

**Production**: Use valid TLS certificates from a trusted CA.

```bash
# Use Let's Encrypt or your organization's CA
export NAAS_CERT=$(cat /path/to/fullchain.pem)
export NAAS_KEY=$(cat /path/to/privkey.pem)
export NAAS_CA_BUNDLE=$(cat /path/to/chain.pem)

docker compose up -d
```

### TLS Configuration

Ensure strong TLS configuration:

```yaml
# docker-compose.override.yml
services:
  api:
    environment:
      - TLS_MIN_VERSION=1.2
      - TLS_CIPHERS=ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384
```

### Certificate Rotation

Rotate certificates before expiration:

```bash
# Check certificate expiration
openssl x509 -in cert.pem -noout -enddate

# Update certificates
export NAAS_CERT=$(cat new-cert.pem)
export NAAS_KEY=$(cat new-key.pem)
docker compose up -d
```

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
  "ip": "192.168.1.1",
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
    "https://naas.example.com/send_command",
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
    "https://naas.example.com/send_command",
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

```bash
# Use strong password
export REDIS_PASSWORD=$(openssl rand -base64 32)

# Disable dangerous commands
docker compose exec redis redis-cli -a $REDIS_PASSWORD \
  CONFIG SET rename-command FLUSHDB ""
```

### Container Isolation

Run containers with minimal privileges:

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

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
# Using nginx (see reverse proxy example above)
# Or implement in application code
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.authorization.username,
    default_limits=["100 per hour", "10 per minute"]
)
```

## Monitoring and Auditing

### Enable Logging

Configure comprehensive logging:

```bash
# Production logging
export APP_ENVIRONMENT=production
docker compose up -d

# Logs include:
# - Authentication attempts
# - API requests
# - Job execution
# - Errors and exceptions
```

### Log Aggregation

Send logs to centralized logging:

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

### Monitor Authentication Failures

Track failed authentication attempts:

```bash
# Check logs for auth failures
docker compose logs api | grep "Authentication failed"

# Set up alerts for repeated failures
# (integrate with your monitoring system)
```

### Audit Trail

NAAS logs include:

- Request ID (X-Request-ID header)
- Username (from Basic Auth)
- Target device IP
- Commands executed
- Timestamps
- Success/failure status

Example log entry:

```text
2026-02-22 19:00:00 INFO [550e8400-e29b-41d4-a716-446655440000] admin@192.168.1.1:22 - Executing: show version
```

## Container Security

### Keep Images Updated

Regularly update NAAS and dependencies:

```bash
# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d
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

```bash
# Stop all NAAS services immediately
docker compose down

# Clear Redis data if compromised
docker compose down -v
```

## Next steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [API Usage Examples](api-usage.md) - Learn the API
- [Quick Start Guide](quickstart.md) - Get started with NAAS
