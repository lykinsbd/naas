# API usage examples

Detailed examples for common NAAS API operations.

!!! warning "Breaking change in v1.3"
    The `delay_factor` parameter was replaced with `read_timeout` (float, seconds).
    Migrate by converting: `delay_factor=2` → `read_timeout=60.0` (approximate).

## Contents

- [Authentication](#authentication)
- [API Key Management](#api-key-management)
- [Send Command](#send-command)
- [Send Configuration](#send-configuration)
- [Job Cancellation](#job-cancellation)
- [Job Status and Results](#job-status-and-results)
- [List Jobs](#list-jobs)
- [Connection Pooling](#connection-pooling)
- [Python Examples](#python-examples)
- [Error Handling](#error-handling)

## Authentication

NAAS supports two authentication methods: HTTP Basic and API key (Bearer JWT).

### Basic Authentication

!!! warning "Deprecation notice"
    Basic auth will be **disabled by default** in v3.0. Migrate to API key
    authentication for programmatic access. Basic auth will remain available
    as an opt-in configuration option.

The original auth method. Credentials are passed through to the network device.

```bash
# Using curl with -u flag
curl -k -u "username:password" https://localhost:8443/healthcheck

# Using Authorization header
curl -k -H "Authorization: Basic $(echo -n 'username:password' | base64)" \
  https://localhost:8443/healthcheck
```

**Important**: Always use HTTPS. Credentials are transmitted to the network device.

### API Key Authentication

API keys are JWTs that authenticate the caller to NAAS independently of device credentials.
Device credentials are provided in the request body instead of the Authorization header.

```bash
# Send a command using an API key
curl -k -X POST https://localhost:8443/v2/send-command \
  -H "Authorization: Bearer eyJhbG..." \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"],
    "username": "admin",
    "password": "device_password"
  }'
```

When using API key auth, `username` and `password` are **required** in the request body.
`enable` is optional (defaults to the password value).

**Key differences from Basic auth:**

- API key identifies the caller; device credentials are separate
- API key users are not subject to TACACS lockout
- Keys embed role and context claims (for future RBAC support)

## API Key Management

Create, list, and revoke API keys. Keys are returned once at creation — store them securely.

All key management endpoints require **Basic auth** — API keys cannot be used to manage
other keys. The Basic auth password must match the `NAAS_ADMIN_SECRET` environment variable.
If `NAAS_ADMIN_SECRET` is not set, key management is disabled.

### Create a Key

```bash
curl -k -X POST https://localhost:8443/v2/api-keys \
  -u "admin:$NAAS_ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin", "ttl": 7776000}'
```

Response:

```json
{
  "key_id": "k-a1b2c3d4e5f6",
  "token": "eyJhbG...",
  "role": "admin",
  "contexts": ["*"],
  "expires_at": "2026-07-04T00:00:00Z"
}
```

| Parameter | Default | Description |
| --- | --- | --- |
| `role` | `admin` | Role: `admin`, `operator`, or `viewer` |
| `contexts` | `["*"]` | Allowed routing contexts |
| `ttl` | `7776000` (90 days) | Expiration in seconds, `0` for no expiry |
| `created_by` | `system` | Creator identity (for audit) |

### List Keys

```bash
curl -k -u "admin:$NAAS_ADMIN_SECRET" https://localhost:8443/v2/api-keys
```

Returns metadata only — tokens are never shown after creation.

### Revoke a Key

```bash
curl -k -X DELETE -u "admin:$NAAS_ADMIN_SECRET" \
  https://localhost:8443/v2/api-keys/k-a1b2c3d4e5f6
```

Revoked keys are immediately rejected on subsequent requests.

## Send Command

Execute show commands on network devices.

### Enqueue Response (202 Accepted)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job enqueued",
  "queue_position": 1,
  "enqueued_at": "2026-03-20T19:00:00+00:00",
  "timeout": 60
}
```

- `queue_position` — approximate position in queue (1 = next to run, may change as jobs complete)
- `enqueued_at` — ISO 8601 timestamp when job was accepted
- `timeout` — maximum seconds the job will run before being killed

### Basic Example

```bash
curl -k -X POST https://localhost:8443/v2/send-command \
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
curl -k -X POST https://localhost:8443/v2/send-command \
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
curl -k -X POST https://localhost:8443/v2/send-command \
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
curl -k -X POST https://localhost:8443/v2/send-command \
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
curl -k -X POST https://localhost:8443/v2/send-command \
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

### Connection Timeout

Control the TCP connection timeout with `conn_timeout` (default: `10.0` seconds):

```bash
curl -k -X POST https://localhost:8443/v2/send-command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"],
    "conn_timeout": 5.0
  }'
```

- `conn_timeout` — seconds to wait for the TCP connection to be established before failing
- `read_timeout` — seconds to wait for a command response after connection is established (default: `30.0`)

Reduce `conn_timeout` for faster failure detection on unreachable hosts. Increase it for devices on high-latency links.

### Supported Platforms

NAAS supports all [Netmiko platforms](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md):

- `cisco_ios` - Cisco IOS
- `cisco_nxos` - Cisco NX-OS
- `arista_eos` - Arista EOS
- `juniper_junos` - Juniper Junos
- `hp_procurve` - HP ProCurve
- And many more...

## Send Configuration

Push configuration changes to devices.

### Basic Configuration

```bash
curl -k -X POST https://localhost:8443/v2/send-config \
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
curl -k -X POST https://localhost:8443/v2/send-config \
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
curl -k -X POST https://localhost:8443/v2/send-config \
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

## Job Deduplication

NAAS automatically deduplicates in-flight jobs. If you submit the same command to the same device while a previous identical job is still running or queued, NAAS returns the existing job_id instead of enqueuing a new one.

Two jobs are considered duplicates when they share the same `host`, `platform`, `commands`, and username.

### Detecting a Deduplicated Response

```json
{
  "job_id": "abc-123",
  "message": "Job enqueued",
  "deduplicated": true,
  "queue_position": 0,
  "enqueued_at": "2026-03-24T18:00:00+00:00",
  "timeout": 60
}
```

When `deduplicated: true`, the `job_id` refers to the existing in-flight job. Poll it normally to get results.

### Disabling Deduplication

Set `JOB_DEDUP_ENABLED=false` to disable deduplication globally. Useful for testing or when you intentionally want parallel identical jobs.

### Idempotency Keys

For client-controlled deduplication (e.g., safe retries on network failure), use `X-Idempotency-Key`:

```bash
curl -k -X POST https://localhost:8443/v2/send-command \
  -H "X-Idempotency-Key: my-unique-key-abc123" \
  -u "admin:password" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

Repeat requests with the same key within 24 hours return the original job_id with `idempotent: true`. Unlike server-side dedup, idempotency keys are opt-in and key-based (not content-based).

## Webhooks

Instead of polling for results, you can provide a `webhook_url` to receive a notification when the job completes.

```bash
curl -k -u admin:admin -X POST https://naas.example.com/v2/send-command \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"],
    "webhook_url": "https://my-app.example.com/naas-callback"
  }'
```

When the job finishes (success or failure), NAAS POSTs a notification to your URL:

```json
{
  "job_id": "abc-123",
  "status": "finished",
  "enqueued_at": "2026-03-20T19:00:00+00:00",
  "completed_at": "2026-03-20T19:00:05+00:00"
}
```

Use `job_id` to fetch the full results from `GET /v2/jobs/{job_id}`.

### Security

- `webhook_url` must be HTTPS (HTTP is rejected)
- The payload contains **only job metadata** — results and credentials are never included
- Your webhook endpoint must be reachable from the NAAS worker network
- Webhook delivery is fire-and-forget: failures are logged but do not affect job status
- No retries in v1.4 (tracked in [#278](https://github.com/lykinsbd/naas/issues/278))

## Dead Letter Queue

Failed jobs are retained in RQ's `FailedJobRegistry` for `JOB_TTL_FAILED` (7 days default). Use these endpoints to inspect and replay them.

### List Failed Jobs

```bash
curl -k -u "admin:password" https://naas.example.com/v2/jobs/failed
```

```json
{
  "jobs": [
    {
      "job_id": "abc-123",
      "host": "192.168.1.1",
      "platform": "cisco_ios",
      "port": 22,
      "failed_at": "2026-03-20T19:00:00+00:00",
      "error": "NetMikoTimeoutException: timed out",
      "func": "naas.library.netmiko_lib.netmiko_send_command"
    }
  ],
  "total": 1
}
```

**Security:** Credentials are never included in the response. Error messages have credential values redacted.

### Replay a Failed Job

Re-enqueue a failed job using your current credentials (stored credentials are never used):

```bash
curl -k -u "admin:password" -X POST \
  https://naas.example.com/v2/jobs/abc-123/replay
```

Returns a standard `202 Accepted` with a new `job_id`. The replayed job uses the caller's credentials, not the original submitter's.

**Note:** Only the original submitter can replay a job (same auth check as job results).

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `FAILED_JOB_MAX_RETAIN` | `500` | Maximum number of failed jobs to retain in the registry |

## Job Cancellation

Cancel running or queued jobs using DELETE.

### Cancel a Job

```bash
curl -k -X DELETE https://localhost:8443/v2/send-command/{job_id} \
  -u "admin:password"
```

**Response codes:**

- `204 No Content` - Job cancelled successfully
- `404 Not Found` - Job ID doesn't exist
- `409 Conflict` - Job already finished (cannot cancel)

### Example

```bash
# Submit a job
JOB_ID=$(curl -k -X POST https://localhost:8443/v2/send-command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}' \
  | jq -r '.job_id')

# Cancel it
curl -k -X DELETE https://localhost:8443/v2/send-command/$JOB_ID \
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
curl -k https://localhost:8443/v2/send-command/550e8400-e29b-41d4-a716-446655440000 \
  -u "admin:password"
```

The `X-Request-ID` header in the 202 response contains the job ID:

```bash
# Capture job ID from response header
JOB_ID=$(curl -k -s -D - -X POST https://localhost:8443/v2/send-command \
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
curl -k -u "admin:password" https://localhost:8443/v2/jobs

# Filter by status
curl -k -u "admin:password" "https://localhost:8443/v2/jobs?status=failed"

# Paginate
curl -k -u "admin:password" "https://localhost:8443/v2/jobs?page=2&per_page=50"
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

## Job Tags

Attach key-value metadata to any job for filtering and auditing. Tags are stored in job metadata and returned in job results and list responses.

### Submitting Tags

```bash
curl -k -X POST https://localhost:8443/v2/send-command \
  -u "admin:password" \
  -d '{
    "host": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"],
    "tags": {"team": "network-ops", "env": "prod", "ticket": "CHG-12345"}
  }'
```

### Constraints

- Maximum 10 tags per job
- Keys and values: alphanumeric, hyphens, underscores, colons (max 64 characters each)
- Tags are optional — omit the field entirely if not needed

### Filtering by Tag

Use `?tag=key:value` on the list jobs endpoint:

```bash
# All jobs tagged team:network-ops
curl -k -u "admin:password" "https://localhost:8443/v2/jobs?tag=team:network-ops"

# Combine with status and pagination
curl -k -u "admin:password" "https://localhost:8443/v2/jobs?tag=env:prod&status=failed&per_page=50"
```

Tags are included in each job object in the response:

```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "finished",
      "created_at": "2026-02-22T19:00:00+00:00",
      "ended_at": "2026-02-22T19:00:05+00:00",
      "tags": {"team": "network-ops", "env": "prod", "ticket": "CHG-12345"}
    }
  ]
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
- **Structured commands** (`/v2/send-command_structured`) - TextFSM state makes pooling unreliable

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
        "https://localhost:8443/v2/send-command",
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
            f"https://localhost:8443/v2/send-command/{job_id}",
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
        "loc": ["host"],
        "msg": "value is not a valid IP address or hostname",
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
            "https://localhost:8443/v2/send-command",
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
