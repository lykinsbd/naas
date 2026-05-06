# NAAS - Netmiko As A Service

NAAS is a REST API wrapper for [Netmiko](https://github.com/ktbyers/netmiko) that runs commands and pushes configurations to network devices over SSH. You submit jobs via HTTP; workers execute them asynchronously and store results in Redis.

## What does it do?

- **Asynchronous job processing** — Commands run in background workers; the API returns immediately with a job ID
- **Broad device support** — Works with any device Netmiko supports (Cisco IOS/NX-OS, Arista EOS, Juniper Junos, Palo Alto, and many others)
- **Python client & CLI** — `pip install naas-client[cli]` for typed API access and terminal usage
- **Authentication & RBAC** — HTTPS, HTTP Basic Auth, JWT API keys with role-based access control (admin/operator/viewer)
- **Context routing** — Route jobs to workers in specific network segments, VRFs, or geographies
- **Job lifecycle** — Query status, wait for completion, cancel in-flight jobs, replay failed jobs
- **Observability** — Prometheus metrics, structured audit logging, OpenTelemetry distributed tracing
- **Reliability** — Circuit breakers, SSH connection pooling, graceful shutdown, queue backpressure

## Quick Example

=== "Python Client"

    ```python
    from naas_client import NaasClient

    with NaasClient("https://naas.example.com", api_key="eyJ...") as client:
        job = client.send_command(
            host="192.168.1.1",
            platform="cisco_ios",
            commands=["show version"],
        )
        result = job.wait(timeout=30)
        print(result.results["show version"])
    ```

=== "CLI"

    ```bash
    naas --url https://naas.example.com --api-key eyJ... \
      send-command --host 192.168.1.1 --platform cisco_ios --wait "show version"
    ```

=== "curl"

    ```bash
    # Submit job
    curl -X POST https://naas.example.com/v2/send-command \
      -H "Authorization: Bearer eyJ..." \
      -H "Content-Type: application/json" \
      -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'

    # Get results
    curl https://naas.example.com/v2/send-command/<job_id> \
      -H "Authorization: Bearer eyJ..."
    ```

Basic Auth also works for quick testing — see the [Quick Start](quickstart.md) for a minimal example.

## Getting Started

- [Quick Start](quickstart.md) — Get NAAS running in 5 minutes with Docker Compose
- [Deployment Overview](deployment/index.md) — Choose a deployment method (Helm, Docker Compose, or manual)
- [Python Client & CLI](client.md) — Library and CLI usage
- [API Usage](api-usage.md) — REST API examples
- [Upgrading to v2.0](upgrading.md) — Migration guide from v1.x

## Project Links

- [GitHub Repository](https://github.com/lykinsbd/naas)
- [Issue Tracker](https://github.com/lykinsbd/naas/issues)
- [Changelog](changelog.md)
