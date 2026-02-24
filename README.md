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

- [Netmiko](https://github.com/ktbyers/netmiko)
- [Flask](https://github.com/pallets/flask)
- [Gunicorn](https://github.com/benoitc/gunicorn)
- [RQ](https://github.com/rq/rq)
- [Redis](https://github.com/antirez/redis)
- [uv](https://github.com/astral-sh/uv)

## Requirements

**For deployment:**

- Docker and Docker Compose
- Server/VM with network access to devices

**For development:**

- Python 3.11+
- See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup

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

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup and prerequisites
- Branching strategy and workflow
- Commit message conventions
- Pull request process
- Code style guidelines
- Testing requirements

## Roadmap

Track planned features and improvements in [GitHub Issues](https://github.com/lykinsbd/naas/issues) and the [v1.1 milestone](https://github.com/lykinsbd/naas/milestone/2).

## License

[License information coming soon]

## Getting Help

- **Documentation**: [docs/](docs/) - Guides and API reference
- **Issues**: [GitHub Issues](https://github.com/lykinsbd/naas/issues) - Bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/lykinsbd/naas/discussions) - Questions and community support
- **Changelog**: [CHANGELOG.md](CHANGELOG.md) - Release notes and version history

## Acknowledgments

Built with ❤️ using:

- [Netmiko](https://github.com/ktbyers/netmiko) by Kirk Byers
- [Flask](https://github.com/pallets/flask) by Pallets
- [RQ](https://github.com/rq/rq) by Vincent Driessen
