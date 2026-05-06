# Deployment Overview

NAAS supports multiple deployment methods. Choose based on your environment and requirements.

## Deployment Methods

| Method | Best For | Prerequisites |
|--------|----------|---------------|
| **[Kubernetes (Helm)](../kubernetes.md)** | Production, team environments, scalability | Kubernetes 1.27+, Helm 3 |
| **[Docker Compose](docker-compose.md)** | Development, small/single-node deployments | Docker, Docker Compose |
| **Manual** | Custom environments, development without Docker | Python 3.11+, Redis 6+, uv |

## Quick Decision Guide

- **Production deployment?** → Use the [Helm chart](../kubernetes.md)
- **Local development or quick evaluation?** → Use [Docker Compose](docker-compose.md) or the [Quick Start](../quickstart.md)
- **Need fine-grained control or no container runtime?** → Manual installation (see below)

## Manual Installation

### Prerequisites

- Python 3.11+
- Redis 6.0+
- uv (Python package manager)

### Steps

```bash
git clone https://github.com/lykinsbd/naas.git
cd naas

# Install dependencies
uv sync

# Set environment variables
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Start Redis
redis-server

# Start API server (in one terminal)
uv run gunicorn -c gunicorn.py naas.app:app

# Start worker (in another terminal)
uv run python worker.py
```

## Configuration

All deployment methods use the same environment variables. See [Environment Variables](environment-variables.md) for the full reference.

## Next Steps

- [Environment Variables](environment-variables.md) — Full configuration reference
- [Security](../security.md) — Production hardening
- [Observability](../observability.md) — Logging, metrics, and tracing
