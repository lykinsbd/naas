# Kubernetes Deployment

NAAS ships plain YAML manifests in `k8s/` for deploying to any Kubernetes cluster.

## Prerequisites

- Kubernetes 1.27+ (or k3d for local dev — see below)
- `kubectl` configured for your cluster
- A container image of NAAS (built and pushed to a registry your cluster can pull from)

> The manifests in `main` reference the image tag for that release. The manifests in `develop`
> use `latest`. For production deployments, always deploy from a tagged release branch and
> verify the image tag in `k8s/api/deployment.yaml` and `k8s/worker/deployment.yaml` matches
> the version you intend to run.

## Local Development with k3d

[k3d](https://k3d.io) runs a lightweight k3s cluster inside Docker — no cloud account needed.

```bash
# Install k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Create a cluster
k3d cluster create naas-dev --port "8443:443@loadbalancer"

# Verify
kubectl get nodes
```

## Applying the Manifests

### 1. Create the secret

```bash
cp k8s/secret.yaml.example k8s/secret.yaml
```

Edit `k8s/secret.yaml` and replace the placeholder values with base64-encoded secrets:

```bash
# Generate base64 values
echo -n 'your-redis-password' | base64
```

> **Never commit `k8s/secret.yaml`** — it is in `.gitignore`.

### 2. Apply in order

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/redis/
kubectl apply -f k8s/api/
kubectl apply -f k8s/worker/
```

### 3. Verify

```bash
kubectl -n naas get pods
kubectl -n naas get svc
```

All pods should reach `Running` status. The API readiness probe hits `/healthcheck` — pods
will not become ready until Redis is up and responding.

## Security Context

Both the API and worker deployments run as UID 1000 (`naas` user, non-root) with all
Linux capabilities dropped. The API retains `NET_BIND_SERVICE` to bind port 443 without
root. TLS certificates are written to `/tmp/` at startup (world-writable, no special
permissions required).

## TLS / Ingress

The NAAS API listens on HTTPS (port 443). The `api` Service is `ClusterIP` — expose it
via your cluster's ingress controller or a `LoadBalancer` service as appropriate for your
environment.

**With a custom certificate:** populate `NAAS_CERT`, `NAAS_KEY`, and optionally
`NAAS_CA_BUNDLE` in `k8s/secret.yaml`. These values must be the **raw PEM content**
(not a file path), base64-encoded for the Kubernetes Secret.

```bash
# Encode a certificate file for use in secret.yaml
cat cert.pem | base64 -w 0
```

The double-encoding works as follows: Kubernetes decodes the base64 value from the Secret
and injects the raw PEM string as an environment variable. NAAS writes that string to disk
at startup for Gunicorn to use.

**Without a certificate:** NAAS generates a self-signed certificate at startup. Suitable
for dev/internal use where clients can skip TLS verification or trust the self-signed cert.

**cert-manager:** If your cluster runs cert-manager, create a `Certificate` resource
targeting the `naas-api` Service and mount the resulting secret into the API pods via
`NAAS_CERT` / `NAAS_KEY` / `NAAS_CA_BUNDLE` environment variables.

## Resource Sizing

The manifests include conservative defaults suitable for a small deployment:

| Component | Memory request | Memory limit | CPU request | CPU limit |
|-----------|---------------|--------------|-------------|-----------|
| API | 256Mi | 768Mi | 100m | 500m |
| Worker | 128Mi | 512Mi | 100m | 500m |
| Redis | 64Mi | 256Mi | 50m | 200m |

Workers are CPU-bound during Netmiko SSH operations. Increase `limits.cpu` and replica
count if you observe throttling under load.

## Production Redis

The bundled Redis manifest is a single-replica Deployment with no persistence — suitable
for dev and testing. **For production, use a managed Redis service** (AWS ElastiCache,
Redis Cloud, DigitalOcean Managed Redis, etc.) or a Redis Operator with replication and
persistence configured.

To use an external Redis, update `REDIS_HOST` and `REDIS_PORT` in `k8s/configmap.yaml`
and remove the `k8s/redis/` manifests.

## Connection Pooling

NAAS reuses SSH connections across sequential jobs to the same device, reducing VTY session
overhead on network equipment. Pooling is enabled by default.

| Variable | Default | Description |
|----------|---------|-------------|
| `CONNECTION_POOL_ENABLED` | `true` | Set to `false` to disable pooling for all devices |
| `CONNECTION_POOL_MAX_SIZE` | `10` | Max pooled connections per worker process |
| `CONNECTION_POOL_IDLE_TIMEOUT` | `300` | Evict connections idle for this many seconds |
| `CONNECTION_POOL_MAX_AGE` | `3600` | Evict connections older than this many seconds |
| `CONNECTION_POOL_KEEPALIVE` | `60` | Paramiko SSH keepalive interval (seconds) |

Disable pooling for specific environments where devices do not handle persistent SSH sessions
well (e.g. older IOS, out-of-band management platforms). Per-device exclusions are tracked
in [#187](https://github.com/lykinsbd/naas/issues/187).

## Scaling Workers

Worker replicas are set to `2` by default. Increase `spec.replicas` in
`k8s/worker/deployment.yaml` based on your job throughput requirements. Each worker
handles one job at a time per process; the number of concurrent jobs equals the number
of worker replicas.

The worker process writes a heartbeat file to `/tmp/worker_heartbeat` every 30 seconds.
The liveness probe checks this file was modified within the last 2 minutes — if the
parent process hangs, Kubernetes will restart the pod. Override the path via the
`WORKER_HEARTBEAT_FILE` environment variable if needed.

## Monitoring

The `/metrics` endpoint on the API pods exposes Prometheus metrics. Configure your
Prometheus instance to scrape port `443` (HTTPS) with the appropriate TLS config, or
use a `ServiceMonitor` if running the Prometheus Operator.

| Metric | Type | Description |
|--------|------|-------------|
| `naas_http_requests_total` | Counter | Total HTTP requests by endpoint, method, and status code |
| `naas_http_request_duration_seconds` | Histogram | Request latency by endpoint |
| `naas_queue_depth` | Gauge | Number of jobs waiting in the RQ queue |
| `naas_workers_active` | Gauge | Number of active RQ worker processes (cached, 10s TTL) |
