# API usage examples

Detailed examples for common NAAS API operations.

!!! warning "Breaking change in v1.3"
    The `delay_factor` parameter was replaced with `read_timeout` (float, seconds).
    Migrate by converting: `delay_factor=2` → `read_timeout=60.0` (approximate).

!!! warning "Deprecation in v1.4: ip field"
    The `ip` field is deprecated. Use `host` instead — it accepts IPv4, IPv6, and hostnames.
    The `ip` field still works but will be removed in v2.0.
    Example: `{"host": "192.168.1.1", ...}` or `{"host": "router1.example.com", ...}`

## Contents

- [Authentication](#authentication)
- [Send Command](#send-command)
- [Send Configuration](#send-configuration)
- [Job Cancellation](#job-cancellation)
- [Job Status and Results](#job-status-and-results)
- [List Jobs](#list-jobs)
- [Connection Pooling](#connection-pooling)
- [Python Examples](#python-examples)
- [Error Handling](#error-handling)

## Authentication

NAAS uses HTTP Basic Authentication. The API passes credentials through to the network device.

```bash
# Using curl with -u flag
curl -k -u "username:password" https://localhost:8443/healthcheck

# Using Authorization header
curl -k -H "Authorization: Basic $(echo -n 'username:password' | base64)" \
  https://localhost:8443/healthcheck
```

**Important**: Always use HTTPS. Credentials are transmitted to the network device.

## Send Command

Execute show commands on network devices.

### Basic Example

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version", "show ip interface brief"]
  }'
```

### With Custom Port

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "port": 2222,
    "platform": "cisco_ios",
    "commands": ["show version"]
  }'
```

### With Enable Password

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "enable": "enable_password",
    "commands": ["show running-config"]
  }'
```

### With Custom Request ID

Track your requests with custom IDs:

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-custom-id-12345" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"]
  }'
```

### With Custom Prompt Matching

Use `expect_string` to override automatic prompt detection with a regex pattern:

```bash
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"],
    "expect_string": "router.*#"
  }'
```

**Use cases:**

- Non-standard prompts that Netmiko doesn't detect
- Commands that change the prompt temporarily
- Devices with custom prompt formats

**Note:** This is an advanced feature. Most users should rely on automatic prompt detection.

### Supported Platforms

NAAS supports all [Netmiko platforms](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md):

- `cisco_ios` - Cisco IOS
- `cisco_nxos` - Cisco NX-OS
- `arista_eos` - Arista EOS
- `juniper_junos` - Juniper Junos
- `hp_procurve` - HP ProCurve
- And many more...

!!! warning "Deprecated: `device_type`"
    The `device_type` field is deprecated and will be removed in v2.0. Use `platform` instead.
    Both fields are accepted in v1.x, but `device_type` logs a deprecation warning.

## Send Configuration

Push configuration changes to devices.

### Basic Configuration

```bash
curl -k -X POST https://localhost:8443/v1/send_config \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": [
      "interface GigabitEthernet0/1",
      "description Uplink to Core",
      "no shutdown"
    ]
  }'
```

### With Save Config

Automatically save configuration after changes:

```bash
curl -k -X POST https://localhost:8443/v1/send_config \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": [
      "interface GigabitEthernet0/1",
      "description Configured via NAAS"
    ],
    "save_config": true
  }'
```

### With Commit (Juniper)

For platforms that require commit:

```bash
curl -k -X POST https://localhost:8443/v1/send_config \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "juniper_junos",
    "commands": [
      "set interfaces ge-0/0/1 description \"Configured via NAAS\""
    ],
    "commit": true
  }'
```

## Job Cancellation

Cancel running or queued jobs using DELETE.

### Cancel a Job

```bash
curl -k -X DELETE https://localhost:8443/v1/send_command/{job_id} \
  -u "admin:password"
```

**Response codes:**

- `204 No Content` - Job cancelled successfully
- `404 Not Found` - Job ID doesn't exist
- `409 Conflict` - Job already finished (cannot cancel)

### Example

```bash
# Submit a job
JOB_ID=$(curl -k -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}' \
  | jq -r '.job_id')

# Cancel it
curl -k -X DELETE https://localhost:8443/v1/send_command/$JOB_ID \
  -u "admin:password"
```

**Use cases:**

- Cancel long-running commands that are no longer needed
- Clean up queued jobs during maintenance
- Stop jobs targeting unreachable devices

**Limitations:**

- Cannot cancel jobs that have already completed
- Cancellation is best-effort (job may complete before cancellation)

## Job Status and Results

### Check Job Status

```bash
curl -k https://localhost:8443/v1/send_command/550e8400-e29b-41d4-a716-446655440000 \
  -u "admin:password"
```

The `X-Request-ID` header in the 202 response contains the job ID:

```bash
# Capture job ID from response header
JOB_ID=$(curl -k -s -D - -X POST https://localhost:8443/v1/send_command \
  -u "admin:password" -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}' \
  | grep -i x-request-id | awk '{print $2}' | tr -d '\r')
```

### Job States

**Queued**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "enqueued_at": "2026-02-22T19:00:00Z"
}
```

**Started**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "enqueued_at": "2026-02-22T19:00:00Z",
  "started_at": "2026-02-22T19:00:01Z"
}
```

**Finished**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "result": "Command output here...",
  "enqueued_at": "2026-02-22T19:00:00Z",
  "started_at": "2026-02-22T19:00:01Z",
  "ended_at": "2026-02-22T19:00:05Z"
}
```

**Failed**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Authentication failed",
  "enqueued_at": "2026-02-22T19:00:00Z",
  "started_at": "2026-02-22T19:00:01Z",
  "ended_at": "2026-02-22T19:00:02Z"
}
```

## List Jobs

List all jobs with optional pagination and status filtering.

```bash
# All jobs (default: page 1, 20 per page)
curl -k -u "admin:password" https://localhost:8443/v1/jobs

# Filter by status
curl -k -u "admin:password" "https://localhost:8443/v1/jobs?status=failed"

# Paginate
curl -k -u "admin:password" "https://localhost:8443/v1/jobs?page=2&per_page=50"
```

Valid `status` values: `queued`, `started`, `finished`, `failed`.

Response:

```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "finished",
      "created_at": "2026-02-22T19:00:00+00:00",
      "ended_at": "2026-02-22T19:00:05+00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1,
    "pages": 1
  }
}
```

## Connection Pooling

NAAS automatically reuses SSH connections to improve performance and reduce load on network devices.

### How It Works

- **Persistent connections**: SSH sessions are kept alive between requests
- **Per-worker pools**: Each worker maintains its own connection pool
- **Automatic cleanup**: Idle connections are closed after timeout
- **Credential isolation**: Connections are keyed by (IP, port, username, password hash)

### Performance Benefits

- **Faster response times**: Eliminates SSH handshake overhead (~1-2 seconds per request)
- **Reduced device load**: Fewer VTY sessions consumed on network devices
- **Better throughput**: Handle more requests per second

### When Pooling is Disabled

Connection pooling is automatically disabled for:

- **Platform autodetect** (`platform: "autodetect"`) - requires clean connection state
- **Structured commands** (`/v1/send_command_structured`) - TextFSM state makes pooling unreliable

### Configuration

Set via environment variables (see [Kubernetes deployment](kubernetes.md#configuration)):

```yaml
CONNECTION_POOL_ENABLED: "true"  # Enable pooling (default)
CONNECTION_POOL_MAX_SIZE: "10"   # Max connections per worker (default)
CONNECTION_POOL_TTL: "300"       # Idle timeout in seconds (default)
```

### Troubleshooting

**Stale connections**: If devices are rebooted, pooled connections may become stale. NAAS detects this and automatically reconnects.

**Credential changes**: Changing a user's password invalidates pooled connections. New requests will establish fresh connections.

**High memory usage**: Reduce `CONNECTION_POOL_MAX_SIZE` if workers consume too much memory.

## Python Examples

### Using Requests Library

```python
import requests
import time
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings()

# NAAS configuration
NAAS_URL = "https://localhost:8443"
AUTH = HTTPBasicAuth("admin", "password")

# Send command
response = requests.post(
    f"{NAAS_URL}/send_command",
    auth=AUTH,
    verify=False,
    json={
        "host": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["show version"]
    }
)

job_id = response.json()["job_id"]
print(f"Job ID: {job_id}")

# Poll for results
while True:
    result = requests.get(
        f"{NAAS_URL}/send_command/{job_id}",
        auth=AUTH,
        verify=False
    ).json()

    status = result["status"]
    print(f"Status: {status}")

    if status == "finished":
        print(f"Result:\n{result['result']}")
        break
    elif status == "failed":
        print(f"Error: {result['error']}")
        break

    time.sleep(1)
```

### Async Python Example

```python
import asyncio
import aiohttp
from aiohttp import BasicAuth

async def send_command(session, device_ip, commands):
    """Send command to device via NAAS."""
    async with session.post(
        "https://localhost:8443/v1/send_command",
        json={
            "host": device_ip,
            "platform": "cisco_ios",
            "commands": commands
        },
        ssl=False
    ) as response:
        data = await response.json()
        return data["job_id"]

async def get_results(session, job_id):
    """Poll for job results."""
    while True:
        async with session.get(
            f"https://localhost:8443/v1/send_command/{job_id}",
            ssl=False
        ) as response:
            data = await response.json()

            if data["status"] in ["finished", "failed"]:
                return data

            await asyncio.sleep(1)

async def main():
    auth = BasicAuth("admin", "password")

    async with aiohttp.ClientSession(auth=auth) as session:
        # Send commands to multiple devices
        devices = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]

        # Submit all jobs
        job_ids = await asyncio.gather(*[
            send_command(session, ip, ["show version"])
            for ip in devices
        ])

        # Get all results
        results = await asyncio.gather(*[
            get_results(session, job_id)
            for job_id in job_ids
        ])

        for device, result in zip(devices, results):
            print(f"\n{device}: {result['status']}")
            if result["status"] == "finished":
                print(result["result"][:100])

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling

### Common HTTP Status Codes

- `200 OK` - Job status retrieved successfully
- `202 Accepted` - Job queued successfully
- `401 Unauthorized` - Missing or invalid credentials
- `403 Forbidden` - Job belongs to another user, or device is locked out
- `404 Not Found` - Job ID not found
- `422 Unprocessable Entity` - Validation failed (invalid IP, unknown platform, etc.)

### Example Error Responses

**Validation error (422)**:

```json
{
  "validation_error": {
    "json": [
      {
        "loc": ["ip"],
        "msg": "value is not a valid IPv4 address",
        "type": "value_error"
      }
    ]
  }
}
```

**Authentication failed (401)**:

```json
{ "message": "Unauthorized" }
```

**Device locked out (403)**:

```json
{ "message": "Forbidden" }
```

### Handling Errors in Python

```python
import requests
from requests.auth import HTTPBasicAuth

def send_command_safe(ip, commands):
    """Send command with error handling."""
    try:
        response = requests.post(
            "https://localhost:8443/v1/send_command",
            auth=HTTPBasicAuth("admin", "password"),
            verify=False,
            json={
                "host": ip,
                "platform": "cisco_ios",
                "commands": commands
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()["job_id"]

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code}")
        print(f"Message: {e.response.json().get('message')}")
    except requests.exceptions.ConnectionError:
        print("Failed to connect to NAAS")
    except requests.exceptions.Timeout:
        print("Request timed out")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return None
```

## API Client Collections

Each NAAS release includes downloadable API client collections on the [GitHub Releases page](https://github.com/lykinsbd/naas/releases):

- `naas-vX.Y.Z.postman_collection.json` — Postman collection with all endpoints
- `naas-vX.Y.Z.openapi.json` — OpenAPI spec for import into any compatible tool

### Postman

1. Download `naas-vX.Y.Z.postman_collection.json` from the release
2. In Postman: **Import** → select the file
3. Set environment variables: `base_url`, `username`, `password`

### Insomnia

1. Download `naas-vX.Y.Z.openapi.json` from the release
2. In Insomnia: **Create** → **Import** → select the file

### Bruno / Other Tools

Import `naas-vX.Y.Z.openapi.json` — any OpenAPI 3.x compatible client works.

## Next steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [Security Best Practices](security.md) - Secure your deployment
- [Full API Reference](https://naas.readthedocs.io/en/latest/api-reference/) - Complete API documentation
