# Batch Operations

Fan out commands or configuration to multiple network devices in a single API call.

## Overview

Batch operations let you submit one set of commands to many devices at once. Instead of making N separate API calls, you send a single request with a list of target devices. NAAS creates individual jobs for each device, tracks them under a shared **batch ID**, and provides aggregate status.

Use batch operations when you need to:

- Run the same show commands across an entire site
- Push identical config to a fleet of switches
- Audit or verify configuration across multiple devices
- Perform bulk changes with a single API call

Each device in the batch gets its own RQ job, so failures on one device don't affect others.

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/v2/send-command/batch` | Fan out show commands to multiple devices |
| POST | `/v2/send-config/batch` | Fan out configuration to multiple devices |
| GET | `/v2/batches/{batch_id}` | Get aggregate status of a batch |

## Send Command Batch

### Request

```bash
curl -k -X POST https://localhost:8443/v2/send-command/batch \
  -H "Authorization: Bearer eyJhbG..." \
  -H "Content-Type: application/json" \
  -d '{
    "commands": ["show version", "show ip interface brief"],
    "platform": "cisco_ios",
    "devices": [
      {"host": "192.168.1.1"},
      {"host": "192.168.1.2"},
      {"host": "192.168.1.3"}
    ],
    "username": "admin",
    "password": "secret"
  }'
```

### Request Body

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `commands` | `string[]` | Yes | Commands to run on each device (max 50) |
| `platform` | `string` | No | Default Netmiko platform for all devices |
| `devices` | `object[]` | Yes | Target devices (max 100) |
| `devices[].host` | `string` | Yes | Device hostname or IP |
| `devices[].port` | `integer` | No | Override SSH port for this device |
| `devices[].platform` | `string` | No | Override platform for this device |
| `devices[].username` | `string` | No | Override credentials for this device |
| `devices[].password` | `string` | No | Override credentials for this device |
| `devices[].enable` | `string` | No | Override enable password for this device |
| `devices[].context` | `string` | No | Override routing context for this device |
| `username` | `string` | No | Default username (required with API key auth) |
| `password` | `string` | No | Default password (required with API key auth) |
| `enable` | `string` | No | Default enable password |
| `port` | `integer` | No | Default SSH port (default: 22) |
| `context` | `string` | No | Default routing context |
| `expect_string` | `string` | No | Custom expect string for all commands |

### Response (202 Accepted)

```json
{
  "batch_id": "batch-a1b2c3d4",
  "job_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002",
    "550e8400-e29b-41d4-a716-446655440003"
  ],
  "total": 3
}
```

## Send Config Batch

### Request

```bash
curl -k -X POST https://localhost:8443/v2/send-config/batch \
  -H "Authorization: Bearer eyJhbG..." \
  -H "Content-Type: application/json" \
  -d '{
    "commands": ["interface loopback99", "description NAAS-MANAGED", "no shutdown"],
    "platform": "cisco_ios",
    "devices": [
      {"host": "192.168.1.1"},
      {"host": "192.168.1.2"}
    ],
    "username": "admin",
    "password": "secret",
    "save_config": true
  }'
```

### Additional Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `commit` | `boolean` | No | Send a commit after config (for commit-based platforms) |
| `save_config` | `boolean` | No | Save running config after applying changes |

### Response (202 Accepted)

Same format as send-command batch.

## Batch Status

### Request

```bash
curl -k https://localhost:8443/v2/batches/batch-a1b2c3d4 \
  -H "Authorization: Bearer eyJhbG..."
```

### Response (200 OK)

```json
{
  "batch_id": "batch-a1b2c3d4",
  "total": 3,
  "completed": 2,
  "failed": 1,
  "pending": 0,
  "status": "partial_failure",
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440001",
      "host": "192.168.1.1",
      "status": "finished",
      "result": "Cisco IOS Software..."
    },
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440002",
      "host": "192.168.1.2",
      "status": "finished",
      "result": "Cisco IOS Software..."
    },
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440003",
      "host": "192.168.1.3",
      "status": "failed",
      "error": "Connection timed out"
    }
  ]
}
```

### Aggregate Status Values

| Status | Meaning |
| --- | --- |
| `pending` | All jobs are still queued or running |
| `complete` | All jobs finished successfully |
| `partial_failure` | Some jobs succeeded, some failed |
| `failed` | All jobs failed |

## Per-Device Credential Overrides

Each device in the `devices` array can specify its own credentials. This is useful when devices have different local accounts or when you need to use different privilege levels.

```json
{
  "commands": ["show running-config"],
  "username": "default_user",
  "password": "default_pass",
  "devices": [
    {"host": "192.168.1.1"},
    {"host": "192.168.1.2", "username": "local_admin", "password": "local_pass"},
    {"host": "192.168.1.3", "enable": "special_enable"}
  ]
}
```

Resolution order for credentials:

1. Per-device `username`/`password`/`enable` (if present)
2. Top-level `username`/`password`/`enable` from request body
3. HTTP Basic credentials (if using Basic auth)

## Per-Device Context Routing

Each device can target a different routing context (i.e., a different RQ worker pool). This lets you fan out commands across multiple regions or security zones in a single batch.

```json
{
  "commands": ["show version"],
  "context": "us-east",
  "devices": [
    {"host": "10.1.1.1"},
    {"host": "10.2.1.1", "context": "us-west"},
    {"host": "10.3.1.1", "context": "eu-central"}
  ]
}
```

Jobs are enqueued to the appropriate context queue. If a device doesn't specify a context, it inherits the top-level `context` (or the default context if none is specified).

!!! note "Context authorization"
    When using API key authentication, your key must have access to all contexts referenced in the batch. If any device targets an unauthorized context, the entire batch is rejected with `403 Forbidden`.

## Limits

| Limit | Default | Environment Variable |
| --- | --- | --- |
| Maximum devices per batch | 100 | `BATCH_MAX_DEVICES` |
| Maximum commands per batch | 50 | `BATCH_MAX_COMMANDS` |

Exceeding either limit returns `422 Unprocessable Entity`:

```json
{
  "error": "Batch exceeds maximum of 100 devices (150 provided)"
}
```

## Rate Limiting

Batch submissions consume rate-limit quota proportional to the number of devices. A batch of 10 devices costs 10 units against your per-caller limit.

If your remaining quota is less than the device count, the entire batch is rejected with `429 Too Many Requests` — no partial submission occurs.

```json
{
  "error": "Rate limit exceeded",
  "detail": "Batch requires 10 units but only 3 remaining in current window"
}
```

## Queue Depth

Before enqueuing jobs, NAAS checks the depth of each target context queue. If any queue exceeds `MAX_QUEUE_DEPTH`, the entire batch is rejected — no jobs are enqueued. This is an **all-or-nothing** check to prevent partial fan-out that could overwhelm a single worker pool.

```json
{
  "error": "Queue depth exceeded for context 'us-east'"
}
```

## Batch Ownership and Access Control

Batches are owned by the caller who submitted them. Only the same caller (matched by credential hash) can query the batch status.

- **API key auth**: ownership is tied to the key identity
- **Basic auth**: ownership is tied to the credential hash

Attempting to access another user's batch returns `403 Forbidden`.

Batch metadata expires from Redis after the same TTL as failed jobs (`JOB_TTL_FAILED`). After expiration, `GET /v2/batches/{batch_id}` returns `404 Not Found`.

## Python Client

```python
import requests

NAAS_URL = "https://naas.example.com:8443"
TOKEN = "eyJhbG..."

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# Submit a batch
payload = {
    "commands": ["show version"],
    "platform": "cisco_ios",
    "devices": [
        {"host": "192.168.1.1"},
        {"host": "192.168.1.2"},
        {"host": "192.168.1.3"},
    ],
    "username": "admin",
    "password": "secret",
}

resp = requests.post(f"{NAAS_URL}/v2/send-command/batch", json=payload, headers=headers, verify=False)
resp.raise_for_status()
batch = resp.json()
print(f"Batch submitted: {batch['batch_id']} ({batch['total']} devices)")

# Poll for status
import time

while True:
    status_resp = requests.get(
        f"{NAAS_URL}/v2/batches/{batch['batch_id']}",
        headers=headers,
        verify=False,
    )
    status = status_resp.json()

    if status["pending"] == 0:
        break

    print(f"Progress: {status['completed']}/{status['total']} complete")
    time.sleep(2)

# Process results
print(f"Final status: {status['status']}")
for job in status["jobs"]:
    if job["status"] == "finished":
        print(f"  {job['host']}: OK")
    else:
        print(f"  {job['host']}: FAILED - {job.get('error', 'unknown')}")
```

## Error Responses

| Status | Cause |
| --- | --- |
| `422 Unprocessable Entity` | Exceeds device or command limit, invalid request body |
| `429 Too Many Requests` | Rate limit exceeded (cost = N devices) or queue depth exceeded |
| `403 Forbidden` | Unauthorized context in batch, or accessing another user's batch |
| `404 Not Found` | Batch ID not found or has expired |

### 422 — Validation Error

```json
{
  "error": "Batch exceeds maximum of 50 commands (75 provided)"
}
```

### 429 — Rate Limit Exceeded

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 30
}
```

### 403 — Forbidden

```json
{
  "error": "You do not have access to this batch"
}
```

### 404 — Not Found

```json
{
  "error": "Batch 'batch-xyz123' not found or has expired"
}
```
