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

1. Check if containers are running:

   ```bash
   docker compose ps
   ```

2. Check container logs:

   ```bash
   docker compose logs api
   ```

3. Verify port mapping:

   ```bash
   docker compose ps | grep api
   # Should show 0.0.0.0:8443->8443/tcp
   ```

4. Check firewall rules:

   ```bash
   sudo ufw status
   sudo firewall-cmd --list-ports
   ```

### NAAS Cannot Reach Network Devices

**Symptom**: Jobs fail with "Connection timeout" or "No route to host"

**Solutions**:

1. Verify network connectivity from NAAS host:

   ```bash
   # From the host
   ping 192.168.1.1
   telnet 192.168.1.1 22
   ```

2. Check Docker network configuration:

   ```bash
   docker compose exec api ping 192.168.1.1
   ```

3. If using custom networks, ensure proper routing:

   ```yaml
   # docker-compose.override.yml
   services:
     api:
       network_mode: host
     worker:
       network_mode: host
   ```

## Authentication Problems

### 401 Unauthorized

**Symptom**: `{"message": "Unauthorized"}`

**Solutions**:

1. Verify credentials are provided:

   ```bash
   # Correct
   curl -k -u "username:password" https://localhost:8443/v1/send_command

   # Wrong - missing credentials
   curl -k https://localhost:8443/v1/send_command
   ```

2. Check for special characters in password:

   ```bash
   # URL encode special characters
   curl -k -u "username:p@ssw0rd!" https://localhost:8443/v1/send_command
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

1. Check Redis container:

   ```bash
   docker compose ps redis
   docker compose logs redis
   ```

2. Verify Redis password:

   ```bash
   # Check environment variable
   docker compose exec api env | grep REDIS_PASSWORD

   # Test Redis connection
   docker compose exec redis redis-cli -a your_password ping
   ```

3. Check Redis connectivity from API:

   ```bash
   docker compose exec api nc -zv redis 6379
   ```

### Redis Out of Memory

**Symptom**: Jobs fail to queue, Redis logs show OOM errors

**Solutions**:

1. Check Redis memory usage:

   ```bash
   docker compose exec redis redis-cli -a your_password INFO memory
   ```

2. Increase Redis memory limit:

   ```yaml
   # docker-compose.override.yml
   services:
     redis:
       command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
   ```

3. Clear old job data:

   ```bash
   docker compose exec redis redis-cli -a your_password FLUSHDB
   ```

## Worker Problems

### No Workers Available

**Symptom**: Jobs stay in "queued" status indefinitely

**Solutions**:

1. Check worker containers:

   ```bash
   docker compose ps worker
   docker compose logs worker
   ```

2. Scale up workers:

   ```bash
   docker compose up -d --scale worker=5
   ```

3. Check worker processes:

   ```bash
   docker compose exec worker ps aux | grep rq
   ```

### Workers Crashing

**Symptom**: Worker containers restart frequently

**Solutions**:

1. Check worker logs for errors:

   ```bash
   docker compose logs worker --tail=100
   ```

2. Common issues:
   - Memory limits too low
   - Network connectivity problems
   - Python dependency issues

3. Increase worker resources:

   ```yaml
   # docker-compose.override.yml
   services:
     worker:
       deploy:
         resources:
           limits:
             memory: 1G
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

   ```bash
   export NAAS_CERT=$(cat /path/to/cert.crt)
   export NAAS_KEY=$(cat /path/to/key.pem)
   docker compose up -d
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

1. Generate new self-signed certificate:

   ```bash
   docker compose down
   docker compose up -d
   # NAAS generates new cert on startup
   ```

2. Or provide your own:

   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout naas.key -out naas.crt

   export NAAS_CERT=$(cat naas.crt)
   export NAAS_KEY=$(cat naas.key)
   docker compose up -d
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

   ```bash
   docker compose up -d --scale worker=10
   ```

### High Memory Usage

**Symptom**: Containers using excessive memory

**Solutions**:

1. Check memory usage:

   ```bash
   docker stats
   ```

2. Reduce worker processes per container:

   ```bash
   export NAAS_WORKER_PROCESSES=50
   docker compose up -d
   ```

3. Set memory limits:

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

## Debugging

### Enable Debug Logging

```bash
# Set environment to dev for debug logs
export APP_ENVIRONMENT=dev
docker compose up -d

# View logs
docker compose logs -f api
docker compose logs -f worker
```

### Check Job Details in Redis

```bash
# Connect to Redis
docker compose exec redis redis-cli -a your_password

# List all jobs
KEYS rq:job:*

# Get job details
HGETALL rq:job:550e8400-e29b-41d4-a716-446655440000

# Check queue length
LLEN rq:queue:default
```

### Test API Endpoints

```bash
# Health check
curl -k https://localhost:8443/healthcheck

# Test with verbose output
curl -k -v -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

### Container Shell Access

```bash
# Access API container
docker compose exec api bash

# Access worker container
docker compose exec worker bash

# Access Redis container
docker compose exec redis sh
```

### Check Python Dependencies

```bash
# List installed packages
docker compose exec api pip list

# Check specific package
docker compose exec api pip show netmiko
```

## Getting help

If you're still experiencing issues:

1. Check [GitHub Issues](https://github.com/lykinsbd/naas/issues) for similar problems
2. Review [API documentation](https://naas.readthedocs.io/en/latest/api-reference/)
3. Open a new issue with:
   - NAAS version
   - Docker/Docker Compose version
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

**Symptom:** `/v1/send_command_structured` returns raw string instead of list[dict].

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
