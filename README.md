# NAAS

**Netmiko As A Service** - REST API wrapper for network device automation

[![Tests](https://github.com/lykinsbd/naas/actions/workflows/test.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/test.yml)
[![Code Quality](https://github.com/lykinsbd/naas/actions/workflows/lint.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/lint.yml)
[![Docker Build](https://github.com/lykinsbd/naas/actions/workflows/build.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/lykinsbd/naas/branch/develop/graph/badge.svg)](https://codecov.io/gh/lykinsbd/naas)
[![Documentation Status](https://readthedocs.org/projects/naas/badge/?version=latest)](https://naas.readthedocs.io/en/latest/?badge=latest)

NAAS provides a production-ready REST API for [Netmiko](https://github.com/ktbyers/netmiko), enabling network automation through HTTP instead of SSH. Run commands on network devices, manage configurations, and integrate with existing tools—all through a simple API.

## Quick Start

```bash
# Start with Docker Compose
git clone https://github.com/lykinsbd/naas.git
cd naas
docker compose up -d

# Send a command
curl -k -X POST https://localhost:8443/v1/send_command \
  -u "username:password" \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

📖 **[Full documentation](https://naas.readthedocs.io/)** | 🚀 **[Installation guide](https://naas.readthedocs.io/en/latest/installation/)** | 📚 **[API reference](https://naas.readthedocs.io/en/latest/api-reference/)**

## Why NAAS?

- **Centralized access** - Single API endpoint for all network devices, simplifying security and compliance
- **HTTPS everywhere** - Proxy SSH/Telnet through HTTPS without complex tunneling
- **Asynchronous execution** - Non-blocking job queue handles long-running commands
- **Multi-platform** - Supports 100+ device types via Netmiko
- **Production-ready** - 100% test coverage, Docker deployment, horizontal scaling

## Key Features

- ✅ RESTful API with async job processing
- 🔒 HTTPS with TLS and HTTP Basic Auth
- 🐳 Docker Compose deployment included
- 📊 Redis-backed job queue (RQ)
- 🚀 Horizontal scaling support
- 🔌 All [Netmiko platforms](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md) supported

## Documentation

- **[Installation](https://naas.readthedocs.io/en/latest/installation/)** - Docker Compose and Kubernetes
- **[API Usage](https://naas.readthedocs.io/en/latest/api-usage/)** - Examples and guides
- **[API Reference](https://naas.readthedocs.io/en/latest/api-reference/)** - Interactive Swagger docs
- **[Contributing](https://naas.readthedocs.io/en/latest/contributing/)** - Development setup
- **[Changelog](https://naas.readthedocs.io/en/latest/changelog/)** - Release notes

## Contributing

Contributions welcome! See the [Contributing Guide](https://naas.readthedocs.io/en/latest/contributing/) for development setup, workflow, and guidelines.

## Support

- **[Documentation](https://naas.readthedocs.io/)** - Guides and API reference
- **[Issues](https://github.com/lykinsbd/naas/issues)** - Bug reports and feature requests
- **[Discussions](https://github.com/lykinsbd/naas/discussions)** - Questions and community support

## License

[License information coming soon]

---

Built with [Netmiko](https://github.com/ktbyers/netmiko) by Kirk Byers
