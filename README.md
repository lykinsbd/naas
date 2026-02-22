# NAAS
Netmiko As A Service

[![Tests](https://github.com/lykinsbd/naas/actions/workflows/test.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/test.yml)
[![Code Quality](https://github.com/lykinsbd/naas/actions/workflows/lint.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/lint.yml)
[![Docker Build](https://github.com/lykinsbd/naas/actions/workflows/build.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/build.yml)

NAAS is a web-based REST API wrapper for the widely-used [Netmiko](https://github.com/ktbyers/netmiko)
 Python library. Netmiko provides structured methods for interacting with Network Devices via SSH/Telnet.

NAAS wraps those Netmiko methods in a RESTful API interface to provide an interface
 for other automation tools (or users) to consume.

NAAS is written in Python 3.11+ and utilizes the following libraries/technologies:
    
* [Netmiko](https://github.com/ktbyers/netmiko) for connectivity to network devices
* [Flask](https://github.com/pallets/flask) for the service/API framework
* [Flask-RESTful](https://github.com/flask-restful/flask-restful) to simplify the REST API structure
* [Gunicorn](https://github.com/benoitc/gunicorn) for the HTTP server
* [RQ](https://github.com/rq/rq) for the background job queueing/execution framework
* [Redis](https://github.com/antirez/redis) for job queueing and other backend K/V store functions
* [uv](https://github.com/astral-sh/uv) for fast, reliable dependency management

Online API documentation can be found here: [NAAS API Documentation](https://lykinsbd.github.io/naas)

## Requirements

- Python 3.11 or higher
- Docker (for containerized deployment)
- Redis server (can be deployed via docker-compose)

## Why Use NAAS?

NAAS provides many benefits when compared to traditional uses of the `netmiko` library natively
in python scripts:

1. NAAS allows you to create a centralized location (or several) with access to network equipment.
 Users, or most commonly automation/orchestration tools, need only have access to NAAS to proxy their
 connections to the network devices. This is often useful in large networks where many different
 users/tools may need to talk to the network devices, but you wish to maintain a small number of
 allowed hosts on the network devices themselves for compliance/security reasons.
2. NAAS essentially proxies specific SSH/Telnet traffic via HTTPS, providing many benefits 
 (not least of which includes scalability).  Users or automation tools do not need to attempt SSH proxying, 
 which introduces considerable management overhead (for SSH config files and so forth) and complexity.
3. NAAS creates a RESTful interface for networking equipment that does not have one.  This is often
 useful if you're attempting to connect an orchestration tool to the network equipment, but that
 tool does not speak SSH.
4. NAAS is asynchronous, calls to `/send_command` or `/send_config` are stored in a job queue, and a
 job_id is returned to the requester.  They can simply call `/send_command/<job_id>` to see job status
 and retrieve any results/errors when it is complete.  This removes the need for blocking on simple command
 execution in automation and allows for greater scale as more workers can simply be added to reach more
 devices or work more quickly.
 
**Note**: While NAAS does provide an HTTP interface to network devices that may not have one today,
it does not (outside of basic TextFSM or Genie support in Netmiko) marshall/structure the returned data
from the network device in any way.  It is incumbent upon the consumer of the API to parse the
raw text response into useful data for their purposes.

## Development Setup

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) for dependency management

### Installation

1. Install uv:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv
```

2. Clone the repository:
```bash
git clone https://github.com/lykinsbd/naas.git
cd naas
```

3. Create a virtual environment and install dependencies:
```bash
# Create virtual environment
uv venv --python 3.11

# Activate it
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e ".[dev]"
```

4. Run tests:
```bash
pytest
```

### Adding Dependencies

To add a new dependency:
```bash
# Edit pyproject.toml to add the package
# Then regenerate lock files
uv pip compile pyproject.toml -o requirements.lock
uv pip compile pyproject.toml --extra dev -o requirements-dev.lock

# Install the new dependency
uv pip install -e .
```


## Running NAAS

### Docker Compose Deployment (Recommended)

The simplest way to run NAAS is using Docker Compose, which launches the API, worker containers, and Redis:

1. [Install Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/) on a server or VM that has management/SSH access to your network devices

2. Clone the repository:
```bash
git clone https://github.com/lykinsbd/naas.git
cd naas
```

3. (Optional) Configure environment variables:
```bash
# Create .env file for custom configuration
cat > .env << EOF
REDIS_PASSWORD=your_secure_password
NAAS_GLOBAL_PORT=8443
NAAS_WORKER_REPLICAS=2
NAAS_WORKER_PROCESSES=100
APP_ENVIRONMENT=production
EOF
```

4. (Optional) Configure TLS certificates:
```bash
# If you have custom certificates
export NAAS_CERT=$(cat /path/to/cert.crt)
export NAAS_KEY=$(cat /path/to/key.pem)
export NAAS_CA_BUNDLE=$(cat /path/to/bundle.crt)
```

5. Start NAAS:
```bash
docker compose up -d
```

6. Verify deployment:
```bash
# Check container status
docker compose ps

# Check logs
docker compose logs -f

# Test healthcheck
curl -k https://localhost:8443/healthcheck
```

7. Scale workers if needed:
```bash
docker compose up -d --scale worker=5
```

### Configuration Options

Environment variables can be set in a `.env` file or exported in your shell:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `redis` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | `mah_redis_pw` | Redis authentication password |
| `NAAS_GLOBAL_PORT` | `8443` | External HTTPS port |
| `NAAS_WORKER_REPLICAS` | `2` | Number of worker containers |
| `NAAS_WORKER_PROCESSES` | `100` | Worker processes per container |
| `APP_ENVIRONMENT` | `dev` | Environment: `dev`, `staging`, or `production` |

### Using External Redis

If you have an existing Redis instance, you can disable the built-in Redis container:

1. Create a `docker-compose.override.yml`:
```yaml
services:
  redis:
    profiles:
      - disabled
  api:
    depends_on: []
  worker:
    depends_on: []
```

2. Set Redis connection environment variables:
```bash
export REDIS_HOST=your-redis-host.example.com
export REDIS_PORT=6379
export REDIS_PASSWORD=your_password
```

3. Start NAAS:
```bash
docker compose up -d
```

### Kubernetes Deployment

Kubernetes manifests are planned for a future release. Track progress in [#28](https://github.com/lykinsbd/naas/issues/28).
