# Quick Start Guide

Get NAAS up and running in 5 minutes using Docker Compose.

!!! warning "Use `/v2/` for new integrations"
    The `/v1/*` and legacy unversioned data-plane routes (`/send_command`, `/send_config`) are deprecated and **will be removed in NAAS v3.0** (sunset: 2027-01-01). All examples below use `/v2/` routes. If you're migrating an existing integration, see [Upgrading to v2.0](upgrading.md).

    The `/healthcheck` endpoint (unversioned) is **not** deprecated — it remains as a permanent operational endpoint for infrastructure probes.

!!! tip "Prefer Kubernetes?"
    If you already have a cluster, skip this and go to the [Helm chart deployment](kubernetes.md).

## Prerequisites

- Docker and Docker Compose installed
- Network access to your target devices

## 1. Clone and start

```bash
git clone https://github.com/lykinsbd/naas.git
cd naas
docker compose up -d
curl -k https://localhost:8443/v2/healthcheck
```

Expected response (version will match your release):

```json
{
  "status": "healthy",
  "version": "2.1.0",
  "uptime_seconds": 42,
  "components": {
    "redis": { "status": "healthy" },
    "queue": { "status": "healthy", "depth": 0 }
  }
}
```

## 2. Send a command

The default `docker-compose.yml` ships with Basic Auth credentials `admin:admin`. These are passed through to your network devices as SSH credentials — replace them with valid device credentials for your environment.

=== "Python Client"

    ```bash
    pip install naas-client
    ```

    ```python
    from naas_client import NaasClient

    with NaasClient("https://localhost:8443", username="admin", password="admin", verify=False) as client:
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
    pip install naas-client[cli]

    naas --url https://localhost:8443 --username admin --password admin --no-verify \
      send-command --host 192.168.1.1 --platform cisco_ios --wait "show version"
    ```

=== "curl"

    ```bash
    curl -k -X POST https://localhost:8443/v2/send-command \
      -u "admin:admin" \
      -H "Content-Type: application/json" \
      -d '{
        "host": "192.168.1.1",
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

    ```bash
    curl -k https://localhost:8443/v2/send-command/550e8400-e29b-41d4-a716-446655440000 \
      -u "admin:admin"
    ```

## 3. Send configuration

=== "CLI"

    ```bash
    naas --url https://localhost:8443 --username admin --password admin --no-verify \
      send-config --host 192.168.1.1 --platform cisco_ios --wait --save-config \
      "interface GigabitEthernet0/1" "description Configured via NAAS"
    ```

=== "curl"

    ```bash
    curl -k -X POST https://localhost:8443/v2/send-config \
      -u "admin:admin" \
      -H "Content-Type: application/json" \
      -d '{
        "host": "192.168.1.1",
        "platform": "cisco_ios",
        "commands": ["interface GigabitEthernet0/1", "description Configured via NAAS"],
        "save_config": true
      }'
    ```

## 4. Check job status

=== "CLI"

    ```bash
    naas --url https://localhost:8443 --username admin --password admin --no-verify \
      jobs list
    ```

=== "curl"

    ```bash
    curl -k https://localhost:8443/v2/jobs -u "admin:admin"
    ```

## Next steps

- [Python Client & CLI](client.md): Full client library and CLI reference
- [API Usage Examples](api-usage.md): Detailed REST API examples
- [Upgrading to v2.0](upgrading.md): Migration guide from v1.x
- [Security](security.md): API keys, RBAC, and TLS configuration
- [Kubernetes Deployment](kubernetes.md): Helm chart and K8s manifests
