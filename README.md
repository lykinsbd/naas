# NAAS

Netmiko As A Service

[![Tests](https://github.com/lykinsbd/naas/actions/workflows/test.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/test.yml)
[![Code Quality](https://github.com/lykinsbd/naas/actions/workflows/lint.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/lint.yml)
[![Docker Build](https://github.com/lykinsbd/naas/actions/workflows/build.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/lykinsbd/naas/branch/develop/graph/badge.svg)](https://codecov.io/gh/lykinsbd/naas)

NAAS is a web-based REST API wrapper for the widely used [Netmiko](https://github.com/ktbyers/netmiko) Python library, providing a RESTful interface for network device automation.

## Quick start

```bash
# Clone and start
git clone https://github.com/lykinsbd/naas.git
cd naas
docker compose up -d

# Send your first command
curl -k -X POST https://localhost:8443/send_command \
  -u "username:password" \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

**[📖 Full Quick Start Guide](docs/quickstart.md)**

## Documentation

- **[Quick Start Guide](docs/quickstart.md)** - Get up and running in 5 minutes
- **[API Usage Examples](docs/api-usage.md)** - Detailed examples with curl and Python
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions
- **[Security Best Practices](docs/security.md)** - Secure your deployment
- **[API Reference](https://lykinsbd.github.io/naas)** - Complete API documentation
- **[Contributing Guide](CONTRIBUTING.md)** - Development setup and guidelines

## Benefits

NAAS provides several advantages over using the `netmiko` library directly:

1. **Centralized Access** - Create a single point of access to network equipment for multiple users and automation tools, simplifying compliance and security
2. **HTTPS Proxy** - Proxy SSH/Telnet traffic via HTTPS without complex SSH tunneling or configuration management
3. **RESTful Interface** - Provide a modern API for network devices that don't have one
4. **Asynchronous Operations** - Non-blocking job queue system allows for greater scale and parallel execution

**Note**: NAAS returns raw text output from devices. Parsing structured data is the responsibility of the API consumer.

## Features

- ✅ **100% Test Coverage** - Unit, integration, and contract tests
- 🔒 **Secure by Default** - HTTPS with TLS, HTTP Basic Authentication
- 🚀 **Scalable** - Horizontal scaling with multiple worker containers
- 🐳 **Container-Ready** - Docker Compose deployment included
- 📊 **Job Queue** - Asynchronous execution with RQ and Redis
- 🔌 **Multi-Platform** - Supports all [Netmiko platforms](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md)

## Technology Stack

- [Netmiko](https://github.com/ktbyers/netmiko) - Network device connectivity
- [Flask](https://github.com/pallets/flask) - Web framework
- [Gunicorn](https://github.com/benoitc/gunicorn) - WSGI HTTP server
- [RQ](https://github.com/rq/rq) - Job queue
- [Redis](https://github.com/antirez/redis) - Queue backend and K/V store
- [uv](https://github.com/astral-sh/uv) - Fast dependency management

## Requirements

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployment)
- Redis server (included in docker-compose.yml)

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/lykinsbd/naas.git
cd naas

# Create virtual environment
uv venv --python 3.11

# Activate it
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest
```

### Development Commands

We use [invoke](https://www.pyinvoke.org/) for common tasks:

```bash
# Code quality
invoke lint          # Run ruff linter
invoke format        # Format code with ruff
invoke typecheck     # Run mypy type checker
invoke check         # Run all code checks

# Testing
invoke test          # Run unit tests
invoke test-all      # Run all tests

# Documentation
invoke docs-lint     # Check markdown style
invoke docs-prose    # Check writing quality (Vale)
invoke docs-links    # Check for broken links
invoke docs-check    # Run all docs checks

# Utilities
invoke clean         # Remove generated files
invoke install       # Install dependencies
```

List all available tasks:

```bash
invoke --list
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

### Using external Redis

If you have an existing Redis instance, you can disable the built-in Redis container.

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

### Kubernetes deployment

Kubernetes manifests are coming in a future release. Track progress in [#28](https://github.com/lykinsbd/naas/issues/28).

## Roadmap

### Future documentation

We're planning to add:

- **Documentation site** - MkDocs hosted on Read the Docs
- **Architecture diagrams** - Visual guides to NAAS internals
- **API client libraries** - Python, Go, and JavaScript clients

Track progress in [GitHub Issues](https://github.com/lykinsbd/naas/issues).

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Branching strategy
- Commit message conventions
- Pull request process
- Code style guidelines

## License

[License information coming soon]

## Support

- **Issues**: [GitHub Issues](https://github.com/lykinsbd/naas/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lykinsbd/naas/discussions)
- **Documentation**: [docs/](docs/)

## Acknowledgments

Built with ❤️ using:

- [Netmiko](https://github.com/ktbyers/netmiko) by Kirk Byers
- [Flask](https://github.com/pallets/flask) by Pallets
- [RQ](https://github.com/rq/rq) by Vincent Driessen
