# Troubleshooting guide

Common issues and solutions for NAAS deployment and operation.

## Contents

- [Connection Issues](#connection-issues)
- [Authentication Problems](#authentication-problems)
- [Redis Issues](#redis-issues)
- [Worker Problems](#worker-problems)
- [SSL/TLS Issues](#ssltls-issues)
- [Performance Issues](#performance-issues)
- [Debugging](#debugging)

## Connection Issues

### Cannot connect to NAAS

**Symptom**: `curl: (7) Failed to connect to localhost port 8443`

**Solutions**:

1. Check if services are running:

    === "Docker Compose"

        ```bash
        docker compose ps
        docker compose logs api
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas get pods
        kubectl -n naas logs deploy/naas-api
        ```

2. Verify port/service exposure:

    === "Docker Compose"

        ```bash
        docker compose ps | grep api
        # Should show 0.0.0.0:8443->8443/tcp
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas get svc
        # For port-forward testing:
        kubectl -n naas port-forward svc/naas-api 8443:443
        ```

3. Check firewall rules:

   ```bash
   sudo ufw status
   sudo firewall-cmd --list-ports
   ```

### NAAS Cannot Reach Network Devices

**Symptom**: Jobs fail with "Connection timeout" or "No route to host"

**Solutions**:

1. Verify network connectivity from NAAS host:

   ```bash
   ping 192.168.1.1
   telnet 192.168.1.1 22
   ```

2. Check connectivity from inside the container/pod:

    === "Docker Compose"

        ```bash
        docker compose exec worker ping 192.168.1.1
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas exec deploy/naas-worker -- ping 192.168.1.1
        ```

3. If using custom networks, ensure proper routing:

    === "Docker Compose"

        ```yaml
        # docker-compose.override.yml
        services:
          worker:
            network_mode: host
        ```

    === "Kubernetes"

        Ensure worker pods have network policies allowing egress to device subnets, or use `hostNetwork: true` in the worker Deployment spec if required.

## Authentication Problems

### 401 Unauthorized

**Symptom**: `{"message": "Unauthorized"}`

**Solutions**:

1. Verify credentials are provided:

   ```bash
   # Correct
   curl -k -u "username:password" https://localhost:8443/v2/send-command

   # Wrong - missing credentials
   curl -k https://localhost:8443/v2/send-command
   ```

2. Check for special characters in password:

   ```bash
   # URL encode special characters
   curl -k -u "username:p@ssw0rd!" https://localhost:8443/v2/send-command
   ```

3. Verify credentials work directly on device:

   ```bash
   ssh username@192.168.1.1
   ```

### Authentication Failed on Device

**Symptom**: Job fails with "Authentication failed"

**Solutions**:

1. Verify credentials are correct for the device
2. Check if account is locked on device
3. Verify SSH is enabled on device
4. Check device access lists/restrictions
5. Try with enable password if required:

   ```json
   {
     "host": "192.168.1.1",
     "platform": "cisco_ios",
     "enable": "enable_password",
     "commands": ["show version"]
   }
   ```

## Redis Issues

### Redis Connection Failed

**Symptom**: `{"status": "degraded", "components": {"redis": {"status": "unhealthy"}, ...}}`

**Solutions**:

1. Check Redis is running:

    === "Docker Compose"

        ```bash
        docker compose ps redis
        docker compose logs redis
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas get pods -l app=redis
        kubectl -n naas logs deploy/redis
        ```

2. Verify Redis password:

    === "Docker Compose"

        ```bash
        docker compose exec api env | grep REDIS_PASSWORD
        docker compose exec redis redis-cli -a your_password ping
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas exec deploy/redis -- redis-cli -a "$REDIS_PASSWORD" ping
        ```

3. Check connectivity from API to Redis:

    === "Docker Compose"

        ```bash
        docker compose exec api nc -zv redis 6379
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas exec deploy/naas-api -- nc -zv naas-redis 6379
        ```

### Redis Out of Memory

**Symptom**: Jobs fail to queue, Redis logs show OOM errors

**Solutions**:

1. Check Redis memory usage:

    === "Docker Compose"

        ```bash
        docker compose exec redis redis-cli -a your_password INFO memory
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas exec deploy/redis -- redis-cli -a "$REDIS_PASSWORD" INFO memory
        ```

2. Increase Redis memory limit:

    === "Docker Compose"

        ```yaml
        # docker-compose.override.yml
        services:
          redis:
            command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas --set redis.resources.limits.memory=2Gi
        ```

3. Clear old job data:

    === "Docker Compose"

        ```bash
        docker compose exec redis redis-cli -a your_password FLUSHDB
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas exec deploy/redis -- redis-cli -a "$REDIS_PASSWORD" FLUSHDB
        ```

## Worker Problems

### No Workers Available

**Symptom**: Jobs stay in "queued" status indefinitely

**Solutions**:

1. Check workers are running:

    === "Docker Compose"

        ```bash
        docker compose ps worker
        docker compose logs worker
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas get pods -l app=naas-worker
        kubectl -n naas logs deploy/naas-worker
        ```

2. Scale up workers:

    === "Docker Compose"

        ```bash
        docker compose up -d --scale worker=5
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas --set worker.replicas=5
        ```

### Workers Crashing

**Symptom**: Worker containers/pods restart frequently

**Solutions**:

1. Check worker logs:

    === "Docker Compose"

        ```bash
        docker compose logs worker --tail=100
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas logs deploy/naas-worker --tail=100
        kubectl -n naas describe pod -l app=naas-worker  # Check events/OOMKilled
        ```

2. Increase worker resources:

    === "Docker Compose"

        ```yaml
        # docker-compose.override.yml
        services:
          worker:
            deploy:
              resources:
                limits:
                  memory: 1G
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas \
          --set worker.resources.limits.memory=1Gi \
          --set worker.resources.limits.cpu=1000m
        ```

## SSL/TLS Issues

### SSL Certificate Errors

**Symptom**: `SSL certificate problem: self signed certificate`

**Solutions**:

1. For testing, disable SSL verification:

   ```bash
   curl -k https://localhost:8443/healthcheck
   ```

2. For production, use valid certificates:

    === "Docker Compose"

        ```bash
        export NAAS_CERT=$(cat /path/to/cert.crt)
        export NAAS_KEY=$(cat /path/to/key.pem)
        docker compose up -d
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas \
          --set secrets.tlsCert="$(cat cert.crt)" \
          --set secrets.tlsKey="$(cat key.pem)"
        ```

3. Add CA certificate to trust store:

   ```bash
   # Linux
   sudo cp naas-ca.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates

   # macOS
   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain naas-ca.crt
   ```

### Certificate expired

**Symptom**: `SSL certificate problem: certificate has expired`

**Solutions**:

1. Regenerate self-signed certificate (restart the service):

    === "Docker Compose"

        ```bash
        docker compose down
        docker compose up -d
        # NAAS generates new cert on startup
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas rollout restart deploy/naas-api
        ```

2. Or provide your own:

    === "Docker Compose"

        ```bash
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
          -keyout naas.key -out naas.crt

        export NAAS_CERT=$(cat naas.crt)
        export NAAS_KEY=$(cat naas.key)
        docker compose up -d
        ```

    === "Kubernetes (Helm)"

        ```bash
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
          -keyout naas.key -out naas.crt

        helm upgrade naas charts/naas \
          --set secrets.tlsCert="$(cat naas.crt)" \
          --set secrets.tlsKey="$(cat naas.key)"
        ```

## Performance Issues

### Slow Job Execution

**Symptom**: Jobs take longer than expected

**Solutions**:

1. Check device response time:

   ```bash
   time ssh username@192.168.1.1 "show version"
   ```

2. Increase delay factor for slow devices:

   ```json
   {
     "host": "192.168.1.1",
     "platform": "cisco_ios",
     "read_timeout": 60.0,
     "commands": ["show version"]
   }
   ```

   **Note:** Prior to v1.3, this parameter was `delay_factor` (integer multiplier).
   Migrate by converting: `delay_factor=2` → `read_timeout=60.0` (approximate).

### Commands That Don't Return to Standard Prompt

**Symptom**: Jobs hang or timeout on commands like `ping`, `traceroute`, or interactive prompts

**Solution**: Use `expect_string` to match the expected output pattern instead of relying on prompt detection:

   ```json
   {
     "host": "192.168.1.1",
     "platform": "cisco_ios",
     "expect_string": "Success rate",
     "commands": ["ping 8.8.8.8"]
   }
   ```

   The `expect_string` is a regex matched against device output. Useful for commands that
   don't return to a standard prompt or have interactive elements.

### Unknown or Heterogeneous Device Types

**Symptom**: Managing devices with unknown or mixed platforms

**Solution**: Use `platform: "autodetect"` to fingerprint devices via SSHDetect:

   ```json
   {
     "host": "192.168.1.1",
     "platform": "autodetect",
     "commands": ["show version"]
   }
   ```

   The detected platform is returned in the job result as `detected_platform`. Note:

- Adds a second SSH connection overhead (fingerprinting + actual commands)
- Not compatible with connection pooling
- Best for discovery workflows, not production automation against known devices

3. Scale workers for parallel execution:

    === "Docker Compose"

        ```bash
        docker compose up -d --scale worker=10
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas --set worker.replicas=10
        ```

### High Memory Usage

**Symptom**: Containers/pods using excessive memory

**Solutions**:

1. Check memory usage:

    === "Docker Compose"

        ```bash
        docker stats
        ```

    === "Kubernetes"

        ```bash
        kubectl -n naas top pods
        ```

2. Set memory limits:

    === "Docker Compose"

        ```yaml
        # docker-compose.override.yml
        services:
          api:
            deploy:
              resources:
                limits:
                  memory: 512M
          worker:
            deploy:
              resources:
                limits:
                  memory: 1G
        ```

    === "Kubernetes (Helm)"

        ```bash
        helm upgrade naas charts/naas \
          --set api.resources.limits.memory=512Mi \
          --set worker.resources.limits.memory=1Gi
        ```

## Debugging

### Enable Debug Logging

=== "Docker Compose"

    ```bash
    LOG_LEVEL=DEBUG docker compose up -d
    docker compose logs -f api
    docker compose logs -f worker
    ```

=== "Kubernetes (Helm)"

    ```bash
    helm upgrade naas charts/naas --set config.LOG_LEVEL=DEBUG
    kubectl -n naas logs -f deploy/naas-api
    kubectl -n naas logs -f deploy/naas-worker
    ```

### Check Job Details in Redis

=== "Docker Compose"

    ```bash
    docker compose exec redis redis-cli -a your_password
    ```

=== "Kubernetes"

    ```bash
    kubectl -n naas exec deploy/redis -- redis-cli -a "$REDIS_PASSWORD"
    ```

Common Redis commands:

```bash
# List all jobs
KEYS rq:job:*

# Get job details
HGETALL rq:job:550e8400-e29b-41d4-a716-446655440000

# Check queue length
LLEN rq:queue:default
```

### Container/Pod Shell Access

=== "Docker Compose"

    ```bash
    docker compose exec api bash
    docker compose exec worker bash
    docker compose exec redis sh
    ```

=== "Kubernetes"

    ```bash
    kubectl -n naas exec -it deploy/naas-api -- bash
    kubectl -n naas exec -it deploy/naas-worker -- bash
    kubectl -n naas exec -it deploy/redis -- sh
    ```

## Getting help

If you're still experiencing issues:

1. Check [GitHub Issues](https://github.com/lykinsbd/naas/issues) for similar problems
2. Review [API documentation](https://naas.readthedocs.io/en/latest/api-reference/)
3. Open a new issue with:
   - NAAS version
   - Deployment method and version (Docker Compose, Helm chart, Kubernetes version)
   - Error messages and logs
   - Steps to reproduce

## Next steps

- [Security Best Practices](security.md) - Secure your deployment
- [API Usage Examples](api-usage.md) - Learn the API
- [Quick Start Guide](quickstart.md) - Get started with NAAS

## Connection Pooling Issues

### Stale Connections

**Symptom:** Commands fail with "Connection closed" or timeout errors after device reboot.

**Cause:** Pooled connection became stale when device rebooted.

**Solution:** NAAS automatically detects and reconnects. If issues persist, disable pooling:

```yaml
CONNECTION_POOL_ENABLED: "false"
```

### High Memory Usage

**Symptom:** Worker containers consuming excessive memory.

**Cause:** Too many pooled connections.

**Solution:** Reduce pool size:

```yaml
CONNECTION_POOL_MAX_SIZE: "5"  # Default is 10
```

## Structured Output Issues

### No Template Found

**Symptom:** `/v2/send-command-structured` returns raw string instead of list[dict].

**Cause:** No TextFSM template exists for the (platform, command) combination.

**Solution:** Supply a custom template:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show custom"],
  "textfsm_template": "Value FIELD (\\S+)\\n\\nStart\\n  ^${FIELD} -> Record"
}
```

Or check [ntc-templates](https://github.com/networktocode/ntc-templates/tree/master/ntc_templates/templates) for available templates.

### Parsing Errors

**Symptom:** Structured output returns empty list or missing fields.

**Cause:** Template doesn't match actual device output format.

**Solution:** Test template with [TextFSM online tool](https://textfsm.nornir.tech/) or supply corrected custom template.

## Platform Autodetect Issues

### Autodetect Fails

**Symptom:** `platform: "autodetect"` returns error "Platform autodetect failed".

**Cause:** Device doesn't respond to SSHDetect probes, or connection fails.

**Solution:** Use explicit platform instead:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show version"]
}
```

### Wrong Platform Detected

**Symptom:** Autodetect returns incorrect platform type.

**Cause:** Device responds ambiguously to SSHDetect probes.

**Solution:** Use explicit platform. Autodetect is best-effort and not 100% accurate.
