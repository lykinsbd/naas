# Kubernetes Deployment

NAAS provides a Helm chart for production Kubernetes deployments, with raw YAML manifests available as an alternative.

## Helm Chart (Recommended)

The Helm chart in `charts/naas/` is the recommended way to deploy NAAS on Kubernetes. It handles namespaces, secrets, config, scaling, and ingress out of the box.

### Prerequisites

- Kubernetes 1.27+
- Helm 3.x
- A container image of NAAS accessible to your cluster

### Quick Start

```bash
helm install naas charts/naas \
  --set secrets.redisPassword=changeme \
  --set secrets.encryptionKey=$(openssl rand -base64 32)
```

Verify:

```bash
kubectl -n naas get pods
```

All pods should reach `Running`. The API readiness probe hits `/healthcheck` — pods will not become ready until Redis is up.

### Common Configurations

#### External Redis

Disable the bundled Redis and point to a managed instance:

```bash
helm install naas charts/naas \
  --set redis.enabled=false \
  --set redis.external.host=redis.prod.internal \
  --set redis.external.port=6379 \
  --set secrets.redisPassword=changeme
```

#### Ingress

```bash
helm install naas charts/naas \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set "ingress.hosts[0].host=naas.example.com" \
  --set "ingress.hosts[0].paths[0].path=/" \
  --set "ingress.hosts[0].paths[0].pathType=Prefix"
```

#### TLS with Custom Certificates

```bash
helm install naas charts/naas \
  --set secrets.tlsCert="$(cat fullchain.pem)" \
  --set secrets.tlsKey="$(cat privkey.pem)" \
  --set secrets.tlsCaBundle="$(cat chain.pem)"
```

Without certificates, NAAS generates a self-signed cert at startup.

**cert-manager:** Create a `Certificate` resource targeting the `naas-api` Service and reference the resulting secret via `secrets.existingSecret`.

#### Context Routing

Deploy workers for specific network contexts:

```yaml
# values-contexts.yaml
worker:
  replicas: 0  # Disable default workers

# Use multiple helm releases or subcharts for context-specific workers.
# Alternatively, deploy additional worker Deployments:
```

For context-based worker isolation, override `config` per worker pool:

```bash
# Corp workers
helm install naas-worker-corp charts/naas \
  --set api.replicas=0 \
  --set redis.enabled=false \
  --set redis.external.host=redis.naas.svc \
  --set config.WORKER_CONTEXTS=corp \
  --set config.NAAS_CONTEXTS=corp

# OOB workers
helm install naas-worker-oob charts/naas \
  --set api.replicas=0 \
  --set redis.enabled=false \
  --set redis.external.host=redis.naas.svc \
  --set config.WORKER_CONTEXTS=oob-dc1,oob-dc2 \
  --set config.NAAS_CONTEXTS=oob-dc1,oob-dc2
```

See [Context Routing](contexts.md) for full details.

#### Scaling

```bash
# Scale workers
helm upgrade naas charts/naas --set worker.replicas=5

# Scale API
helm upgrade naas charts/naas --set api.replicas=4
```

Each worker pod runs `worker.processes` RQ processes (default: 10). Total job concurrency = `worker.replicas × worker.processes`.

#### OpenTelemetry

```bash
helm install naas charts/naas \
  --set config.OTEL_ENABLED=true \
  --set config.OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.monitoring:4317
```

### Upgrade and Rollback

```bash
# Upgrade to new values or chart version
helm upgrade naas charts/naas -f values-prod.yaml

# Rollback to previous release
helm rollback naas

# Uninstall
helm uninstall naas
```

### Values Reference

| Value | Default | Description |
| ----- | ------- | ----------- |
| `image.repository` | `ghcr.io/lykinsbd/naas` | Container image |
| `image.tag` | Chart `appVersion` | Image tag |
| `namespace` | `naas` | Target namespace |
| `api.replicas` | `2` | API pod replicas |
| `api.port` | `443` | API listen port |
| `api.resources.limits.memory` | `768Mi` | API memory limit |
| `api.resources.limits.cpu` | `500m` | API CPU limit |
| `worker.replicas` | `2` | Worker pod replicas |
| `worker.processes` | `10` | RQ processes per worker pod |
| `worker.metricsPort` | `9090` | Worker metrics port |
| `worker.resources.limits.memory` | `512Mi` | Worker memory limit |
| `worker.resources.limits.cpu` | `500m` | Worker CPU limit |
| `config.*` | *(see below)* | Application env vars (injected as ConfigMap) |
| `secrets.existingSecret` | `""` | Use an existing K8s Secret |
| `secrets.redisPassword` | `""` | Redis password |
| `secrets.encryptionKey` | `""` | Credential encryption key |
| `secrets.tlsCert` | `""` | TLS certificate (PEM) |
| `secrets.tlsKey` | `""` | TLS private key (PEM) |
| `secrets.tlsCaBundle` | `""` | TLS CA bundle (PEM) |
| `redis.enabled` | `true` | Deploy bundled Redis |
| `redis.external.host` | `""` | External Redis host |
| `redis.external.port` | `6379` | External Redis port |
| `ingress.enabled` | `false` | Create Ingress resource |
| `ingress.className` | `""` | Ingress class |
| `service.type` | `ClusterIP` | Service type |

All `config.*` values map to environment variables. See [Environment Variables](deployment/environment-variables.md) for the full list.

### Production Redis

The bundled Redis is a single-replica deployment with no persistence — suitable for dev/test. **For production, use a managed Redis** (AWS ElastiCache, Redis Cloud, etc.) with `redis.enabled=false`.

## Raw Manifests (Alternative)

If you cannot use Helm, plain YAML manifests are available in `k8s/`.

### Applying Manifests

```bash
# Create the secret from the example
cp k8s/secret.yaml.example k8s/secret.yaml
# Edit k8s/secret.yaml with base64-encoded values

# Apply in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/redis/
kubectl apply -f k8s/api/
kubectl apply -f k8s/worker/
```

> **Never commit `k8s/secret.yaml`** — it is in `.gitignore`.

### Scaling Workers (Manifests)

Edit `spec.replicas` in `k8s/worker/deployment.yaml`, or:

```bash
kubectl -n naas scale deploy/naas-worker --replicas=5
```

## Local Development with k3d

[k3d](https://k3d.io) runs a lightweight k3s cluster inside Docker — no cloud account needed.

```bash
# Install k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Create a cluster
k3d cluster create naas-dev --port "8443:443@loadbalancer"

# Deploy with Helm
helm install naas charts/naas \
  --set secrets.redisPassword=devpassword \
  --set secrets.encryptionKey=dev-encryption-key-32bytes!!

# Verify
kubectl -n naas get pods
curl -k https://localhost:8443/healthcheck
```

## Security Context

Both API and worker pods run as UID 1000 (`naas` user, non-root) with all Linux capabilities dropped. The API retains `NET_BIND_SERVICE` to bind port 443 without root.

## Monitoring

The `/metrics` endpoint on API pods exposes Prometheus metrics. Configure scraping via a `ServiceMonitor` (Prometheus Operator) or static config:

```yaml
scrape_configs:
  - job_name: naas
    static_configs:
      - targets: ['naas-api.naas.svc:443']
    scheme: https
    tls_config:
      insecure_skip_verify: true
```

| Metric | Type | Description |
| ------ | ---- | ----------- |
| `naas_http_requests_total` | Counter | HTTP requests by endpoint, method, status |
| `naas_http_request_duration_seconds` | Histogram | Request latency by endpoint |
| `naas_queue_depth` | Gauge | Jobs waiting in queue |
| `naas_workers_active` | Gauge | Active RQ worker processes |

## Connection Pooling

Workers reuse SSH connections across sequential jobs to the same device. Configure via `config.*` values:

| Value | Default | Description |
| ----- | ------- | ----------- |
| `config.CONNECTION_POOL_ENABLED` | `true` | Enable pooling |
| `config.CONNECTION_POOL_MAX_SIZE` | `10` | Max connections per worker process |
| `config.CONNECTION_POOL_IDLE_TIMEOUT` | `300` | Evict idle connections (seconds) |
| `config.CONNECTION_POOL_MAX_AGE` | `3600` | Evict old connections (seconds) |
| `config.CONNECTION_POOL_KEEPALIVE` | `60` | SSH keepalive interval (seconds) |
