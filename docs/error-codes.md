# Error Codes

Job results include optional `error_code` and `error_retryable` fields for machine-parseable error classification. These are additive — the existing `error` field (human-readable string) is unchanged.

## Response Fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `error` | `string \| null` | Human-readable error message (unchanged) |
| `error_code` | `string \| null` | Machine-parseable error code from the table below |
| `error_retryable` | `bool \| null` | Whether the caller should retry the request |

All three fields are `null` when the job succeeds without error.

## Error Code Reference

| Code | Cause | Retryable | Description |
| ---- | ----- | --------- | ----------- |
| `CONNECTION_TIMEOUT` | Device unreachable | ✅ | TCP connection timed out. Check host/port, network path, or device availability. |
| `AUTH_FAILURE` | Bad credentials | ❌ | Device rejected the username/password. Triggers TACACS lockout tracking. |
| `SSH_ERROR` | SSH protocol failure | ✅ | SSH handshake or key exchange failed. May indicate incompatible SSH versions. |
| `CONFIG_REJECTED` | Invalid config commands | ❌ | Device rejected one or more configuration commands (syntax error, invalid input). |
| `CIRCUIT_OPEN` | Too many recent failures | ✅ | Circuit breaker is open for this device due to repeated connection failures. Retry after the breaker resets. |
| `AUTODETECT_FAILED` | Platform detection failed | ❌ | SSHDetect could not determine the device platform. Specify `platform` explicitly. |
| `UNKNOWN` | Unhandled exception | ❌ | An unexpected error occurred in the worker. Check server logs. |

## Example Response

```json
{
  "job_id": "abc-123",
  "status": "finished",
  "results": null,
  "error": "TCP connection to device failed.\n\nDevice settings: cisco_ios 192.168.1.1:22",
  "error_code": "CONNECTION_TIMEOUT",
  "error_retryable": true,
  "detected_platform": null,
  "tags": null
}
```

## Client Library

The Python client raises specific exception subclasses based on `error_code`:

```python
from naas_client import NaasClient
from naas_client.exceptions import (
    NaasJobError,          # base — UNKNOWN or unmapped codes
    NaasConnectionError,   # CONNECTION_TIMEOUT, SSH_ERROR
    NaasDeviceAuthError,   # AUTH_FAILURE
    NaasConfigError,       # CONFIG_REJECTED
    NaasCircuitOpenError,  # CIRCUIT_OPEN
)

with NaasClient("https://naas.example.com", api_key="eyJ...") as client:
    job = client.send_command(host="10.0.0.1", platform="cisco_ios", commands=["show version"])
    try:
        result = job.wait(timeout=30)
    except NaasConnectionError as e:
        print(f"Device unreachable: {e.error_code}, retry={e.error_retryable}")
    except NaasDeviceAuthError:
        print("Bad credentials — do not retry")
    except NaasJobError as e:
        print(f"Other failure: {e.error_code}")
```

All subclasses extend `NaasJobError`, so catching `NaasJobError` still works as a catch-all.

## Backward Compatibility

- `error` field: unchanged, still `str | null`
- `error_code` / `error_retryable`: new optional fields, `null` when no error
- Old jobs in Redis (pre-upgrade): new fields returned as `null`
- Existing client code catching `NaasJobError` continues to work — subclasses are additive
