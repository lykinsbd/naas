# Python Client Library

`naas-client` is the official Python client for NAAS. It provides typed, ergonomic access to the v2 API with both synchronous and asynchronous support.

## Installation

```bash
pip install naas-client
```

## Quick Start

```python
from naas_client import NaasClient

with NaasClient("https://naas.example.com", username="admin", password="secret") as client:
    job = client.send_command(
        host="192.168.1.1",
        platform="cisco_ios",
        commands=["show version", "show interfaces"],
    )
    result = job.wait(timeout=30)
    print(result.results["show version"])
```

## Authentication

**Basic auth:**

```python
client = NaasClient(
    "https://naas.example.com",
    username="admin",
    password="secret",
)
```

**API key:**

```python
client = NaasClient(
    "https://naas.example.com",
    api_key="your-jwt-token",
)
```

## Async Usage

```python
from naas_client import AsyncNaasClient

async with AsyncNaasClient("https://naas.example.com", api_key="key") as client:
    job = await client.send_command(
        host="10.0.0.1",
        platform="cisco_ios",
        commands=["show version"],
    )
    result = await job.wait(timeout=30)
```

## Job Polling

Submit methods return a `Job` (or `AsyncJob`) object with polling capabilities:

```python
job = client.send_command(host="10.0.0.1", platform="cisco_ios", commands=["show version"])

# Block until complete (raises NaasJobError on failure, NaasTimeoutError on timeout)
result = job.wait(timeout=60, interval=2.0)

# Or poll manually
result = job.poll()
if job.is_complete:
    print(result.results)
if job.is_failed:
    print(result.error)

# Cancel or replay
job.cancel()
new_job = job.replay()
```

## API Methods

### Commands and Configuration

| Method | Description |
| ------ | ----------- |
| `send_command(**kwargs)` | Submit a command job |
| `send_command_structured(**kwargs)` | Submit a structured command job (TextFSM/TTP) |
| `send_config(**kwargs)` | Submit a config job |
| `get_command_result(job_id)` | Get command job result |
| `get_config_result(job_id)` | Get config job result |

### Job Management

| Method | Description |
| ------ | ----------- |
| `list_jobs(page, per_page, status, tag)` | List jobs with pagination |
| `cancel_job(job_id)` | Cancel a job |
| `replay_job(job_id)` | Re-enqueue a failed job |
| `failed_jobs()` | List failed jobs |

### Contexts and API Keys

| Method | Description |
| ------ | ----------- |
| `list_contexts()` | List routing contexts |
| `list_api_keys()` | List API keys (metadata only) |
| `create_api_key(role, contexts, ttl)` | Create an API key |
| `delete_api_key(key_id)` | Revoke an API key |
| `rotate_api_key(key_id)` | Rotate an API key |
| `healthcheck()` | Check server health |

## Error Handling

All exceptions inherit from `NaasError`:

```python
from naas_client import NaasAuthError, NaasApiError, NaasTimeoutError, NaasJobError

try:
    result = job.wait(timeout=30)
except NaasAuthError:
    # 401 or 403
    print("Authentication failed")
except NaasTimeoutError:
    # Request or wait timeout
    print("Timed out")
except NaasJobError as e:
    # Job completed with failed status
    print(f"Job {e.job_id} failed: {e.error}")
except NaasApiError as e:
    # Any other HTTP error
    print(f"API error {e.status_code}: {e.body}")
```

## Configuration

```python
client = NaasClient(
    "https://naas.example.com",
    username="admin",
    password="secret",
    verify=False,       # Disable TLS verification
    timeout=60.0,       # Request timeout in seconds
    max_retries=5,      # Retries on transient failures (5xx, connection errors)
)
```

## Compatibility

- **Python**: 3.11+
- **NAAS server**: ≥ 2.0
- **Versioning**: `naas-client` uses independent SemVer (see [ADR 0001](adr/0001-python-client-library-integration.md))
