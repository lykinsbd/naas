# Quick start guide

Get NAAS up and running in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Network access to your target devices

## 1. Clone and start

```bash
# Clone the repository
git clone https://github.com/lykinsbd/naas.git
cd naas

# Start NAAS with default configuration
docker compose up -d

# Verify it's running
curl -k https://localhost:8443/healthcheck
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.1.0",
  "uptime_seconds": 42,
  "components": {
    "redis": { "status": "healthy" },
    "queue": { "status": "healthy", "depth": 0 }
  }
}
```

## 2. Send a command

Send a command to a network device:

```bash
# Send command (replace with your device credentials)
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "device_username:device_password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"]
  }'
```

Response:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job enqueued"
}
```

## 3. Get results

Check the job status and retrieve results:

```bash
# Get results (use the job_id from previous response)
curl -k https://localhost:8443/v1/send_command/550e8400-e29b-41d4-a716-446655440000 \
  -u "device_username:device_password"
```

Response when complete:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "result": "Cisco IOS Software, C2960 Software...",
  "enqueued_at": "2026-02-22T19:00:00Z",
  "started_at": "2026-02-22T19:00:01Z",
  "ended_at": "2026-02-22T19:00:05Z"
}
```

## 4. Send configuration

Push configuration changes:

```bash
curl -k -X POST https://localhost:8443/v1/send_config \
  -u "device_username:device_password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": [
      "interface GigabitEthernet0/1",
      "description Configured via NAAS"
    ],
    "save_config": true
  }'
```

## Next steps

- [API Usage Examples](api-usage.md) - More detailed examples
- [Security Best Practices](security.md) - Secure your deployment
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [API Documentation](https://naas.readthedocs.io/en/latest/api-reference/) - Full API reference
