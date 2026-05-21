# Platform Autodetect

NAAS can fingerprint an unknown device and pick the right Netmiko driver automatically.
Set `platform: "autodetect"` on any command request and NAAS uses Netmiko's
[SSHDetect](https://github.com/ktbyers/netmiko/blob/develop/netmiko/ssh_autodetect.py)
to identify the device type before running your commands.

This is most useful for **discovery workflows** — inventory sweeps, onboarding
unknown devices, validating a device list — where you don't yet know what each
host runs.

## Usage

Autodetect works on both `/v2/send-command` and `/v2/send-command-structured`.
Pass `"autodetect"` instead of an explicit platform string:

```bash
curl -k -u "username:password" https://localhost:8443/v2/send-command \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.1",
    "platform": "autodetect",
    "commands": ["show version"]
  }'
```

The detected platform is returned in the job result as `detected_platform`:

```json
{
  "job_id": "...",
  "status": "finished",
  "detected_platform": "cisco_nxos",
  "results": {
    "show version": "Cisco Nexus Operating System (NX-OS) Software\n..."
  }
}
```

NAAS recognizes the same platform names Netmiko does — `cisco_ios`,
`cisco_nxos`, `cisco_xr`, `arista_eos`, `juniper_junos`, `hp_procurve`, etc.
The full list is in the
[Netmiko PLATFORMS file](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md).

## Tradeoffs

Autodetect is a probe-then-execute pattern. That has costs you should know about
before turning it on for a high-volume workload:

- **Extra SSH round-trip.** SSHDetect opens its own session, runs identification
  commands, and closes it before the real command session opens. Expect 1–3
  extra seconds per request compared to a known platform.
- **Connection pooling is disabled.** Pooled connections are bound to a specific
  driver, so autodetect can't reuse them. See
  [Connection Pooling](api-usage.md#connection-pooling) for details.
- **Best-effort, not guaranteed.** Some devices respond ambiguously to SSHDetect
  probes. If detection fails or returns the wrong platform, NAAS surfaces an
  error — see [Troubleshooting: Platform Autodetect Issues](troubleshooting.md#platform-autodetect-issues).

## When to use it

**Use `platform: "autodetect"` when:**

- Building a discovery or inventory workflow against a heterogeneous estate
- Onboarding a new device without confirmed platform metadata
- Auditing a device list against expected platform types

**Use an explicit platform when:**

- You already know what the device runs (the common case)
- You're running production automation at any volume — the SSH overhead and
  loss of pooling adds up fast
- You can't tolerate occasional misidentification

## See also

- [API Usage — Connection pooling interaction](api-usage.md#connection-pooling)
- [Troubleshooting — Platform Autodetect Issues](troubleshooting.md#platform-autodetect-issues)
- [Error Codes — `AUTODETECT_FAILED`](error-codes.md)
