# API usage examples

Detailed examples for common NAAS API operations.

## Table of contents

- [Authentication](#authentication)
- [Send Command](#send-command)
- [Send Configuration](#send-configuration)
- [Job Status and Results](#job-status-and-results)
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
curl -k -X POST https://localhost:8443/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version", "show ip interface brief"]
  }'
```

### With Custom Port

```bash
curl -k -X POST https://localhost:8443/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "port": 2222,
    "platform": "cisco_ios",
    "commands": ["show version"]
  }'
```

### With Enable Password

```bash
curl -k -X POST https://localhost:8443/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "enable": "enable_password",
    "commands": ["show running-config"]
  }'
```

### With Custom Request ID

Track your requests with custom IDs:

```bash
curl -k -X POST https://localhost:8443/send_command \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-custom-id-12345" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version"]
  }'
```

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
curl -k -X POST https://localhost:8443/send_config \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
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
curl -k -X POST https://localhost:8443/send_config \
  -u "admin:password" \
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

### With Commit (Juniper)

For platforms that require commit:

```bash
curl -k -X POST https://localhost:8443/send_config \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "juniper_junos",
    "commands": [
      "set interfaces ge-0/0/1 description \"Configured via NAAS\""
    ],
    "commit": true
  }'
```

## Job Status and Results

### Check Job Status

```bash
curl -k https://localhost:8443/send_command/550e8400-e29b-41d4-a716-446655440000 \
  -u "admin:password"
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
        "ip": "192.168.1.1",
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
        "https://localhost:8443/send_command",
        json={
            "ip": device_ip,
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
            f"https://localhost:8443/send_command/{job_id}",
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
- `400 Bad Request` - Invalid request format
- `401 Unauthorized` - Missing or invalid credentials
- `404 Not Found` - Job ID not found
- `422 Unprocessable Entity` - Invalid parameters
- `429 Too Many Requests` - Rate limited

### Example Error Responses

**Invalid IP Address**:

```json
{
  "message": "Invalid IP address format"
}
```

**Authentication Failed**:

```json
{
  "message": "Authentication failed"
}
```

**Missing Required Field**:

```json
{
  "message": "Missing required field: commands"
}
```

### Handling Errors in Python

```python
import requests
from requests.auth import HTTPBasicAuth

def send_command_safe(ip, commands):
    """Send command with error handling."""
    try:
        response = requests.post(
            "https://localhost:8443/send_command",
            auth=HTTPBasicAuth("admin", "password"),
            verify=False,
            json={
                "ip": ip,
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

## Next steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues
- [Security Best Practices](security.md) - Secure your deployment
- [Full API Reference](https://lykinsbd.github.io/naas) - Complete API documentation
