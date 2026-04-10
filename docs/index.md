# NAAS - Netmiko As A Service

Welcome to the NAAS documentation! NAAS is a REST API wrapper for [Netmiko](https://github.com/ktbyers/netmiko), enabling network device automation through a simple HTTP interface.

## What is NAAS?

NAAS provides a production-ready API for executing commands and configurations on network devices. It handles:

- **Asynchronous job processing**: Commands run in background workers
- **Multiple device platforms**: Supports all Netmiko-compatible devices (Cisco, Arista, Juniper, etc.)
- **Python client & CLI**: `pip install naas-client[cli]` for typed API access and terminal usage
- **Secure authentication**: HTTPS, Basic Auth, JWT API keys with RBAC
- **Context routing**: Isolate workloads across dedicated worker pools
- **Job tracking**: Query status, wait for completion, cancel, replay
- **Production features**: Prometheus metrics, audit logging, circuit breakers, connection pooling

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

## Features

- ✅ REST API for network device automation (v2 with hyphenated routes)
- ✅ Python client library with sync and async support
- ✅ CLI tool with human and JSON output modes
- ✅ Asynchronous job processing with Redis Queue (RQ)
- ✅ Support for 100+ device platforms via Netmiko
- ✅ JWT API key authentication with RBAC (admin/operator/viewer)
- ✅ Context-based routing and worker isolation
- ✅ Prometheus metrics (API and worker)
- ✅ Helm chart for Kubernetes deployment
- ✅ Structured audit logging
- ✅ Circuit breakers and SSH connection pooling
- ✅ Credential encryption at rest

## Getting Started

- [Quick Start](quickstart.md): Get NAAS running in 5 minutes
- [Python Client](client.md): Library and CLI usage
- [API Usage](api-usage.md): REST API examples
- [Upgrading to v2.0](upgrading.md): Migration guide from v1.x

## Project Links

- [GitHub Repository](https://github.com/lykinsbd/naas)
- [Issue Tracker](https://github.com/lykinsbd/naas/issues)
- [Changelog](changelog.md)
