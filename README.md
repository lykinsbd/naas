# NAAS

**Netmiko As A Service** - REST API wrapper for network device automation

[![Tests](https://github.com/lykinsbd/naas/actions/workflows/test.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/test.yml)
[![Code Quality](https://github.com/lykinsbd/naas/actions/workflows/lint.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/lint.yml)
[![Docker Build](https://github.com/lykinsbd/naas/actions/workflows/build.yml/badge.svg)](https://github.com/lykinsbd/naas/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/lykinsbd/naas/branch/develop/graph/badge.svg)](https://codecov.io/gh/lykinsbd/naas)
[![Documentation Status](https://readthedocs.org/projects/naas/badge/?version=stable)](https://naas.readthedocs.io/en/stable/?badge=stable)

NAAS provides a production-ready REST API for [Netmiko](https://github.com/ktbyers/netmiko), enabling network automation through HTTP instead of SSH. Run commands on network devices, manage configurations, and integrate with existing tools—all through a simple API.

## Quick Start

```bash
# Start with Docker Compose
git clone https://github.com/lykinsbd/naas.git
cd naas
docker compose up -d

# Send a command
curl -k -X POST https://localhost:8443/v2/send-command \
  -u "username:password" \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.1", "platform": "cisco_ios", "commands": ["show version"]}'
```

📖 **[Full documentation](https://naas.readthedocs.io/)** | 🚀 **[Installation guide](https://naas.readthedocs.io/en/stable/installation/)** | 📚 **[API reference](https://naas.readthedocs.io/en/stable/api-reference/)**

> **⚠️ Deprecation notice — `/v1/` and unversioned routes**
>
> The `/v1/*` routes and legacy unversioned aliases (`/send_command`, `/send_config`, `/healthcheck`) are deprecated and **will be removed in NAAS v3.0** (sunset date: **2027-01-01**). All new integrations should use `/v2/` routes with hyphenated paths (`/v2/send-command` etc.). See the [migration guide](https://naas.readthedocs.io/en/stable/upgrading/) for details.

## Why NAAS?

- **Centralized access** - Single API endpoint for all network devices, simplifying security and compliance
- **HTTPS everywhere** - Proxy SSH/Telnet through HTTPS without complex tunneling
- **Asynchronous execution** - Non-blocking job queue handles long-running commands
- **Multi-platform** - Supports 100+ device types via Netmiko
- **Production-ready** - 100% test coverage, Docker deployment, horizontal scaling

## Key Features

### v2 (Current)

- 🔐 **API key authentication (JWT)** - Token-based access with role-based access control (admin/operator/viewer)
- 🎯 **Context authorization** - Scope API keys to specific routing contexts
- 🔒 **Credential encryption at rest** - Device credentials encrypted in Redis
- 📡 **SSE job streaming** - Server-sent events for real-time job updates
- 🪝 **Webhook HMAC + retry** - Signed payloads with exponential-backoff redelivery
- 📊 **OpenTelemetry tracing** - Distributed tracing for production observability
- 🤖 **MCP server** - AI-assistant integration via Model Context Protocol

### Core Features

- ✨ TextFSM structured output, platform autodetect, connection pooling
- 📊 Prometheus metrics at `/metrics`
- 🛑 Job cancellation and replay
- 📝 Structured audit logging
- ✅ RESTful API with async job processing
- 🔒 HTTPS with TLS
- 🐳 Docker Compose and Kubernetes deployment
- 📊 Redis-backed job queue (RQ)
- 🚀 Horizontal scaling support
- 🔌 All [Netmiko platforms](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md) supported
- 🔐 Circuit breaker pattern for failing devices
- 🎯 100% test coverage

## Documentation

- **[Installation](https://naas.readthedocs.io/en/stable/installation/)** - Docker Compose and Kubernetes
- **[API Usage](https://naas.readthedocs.io/en/stable/api-usage/)** - Examples and guides
- **[API Reference](https://naas.readthedocs.io/en/stable/api-reference/)** - Interactive Swagger docs
- **[Contributing](https://naas.readthedocs.io/en/stable/contributing/)** - Development setup
- **[Changelog](https://naas.readthedocs.io/en/stable/changelog/)** - Release notes

## Contributing

Contributions welcome! See the [Contributing Guide](https://naas.readthedocs.io/en/stable/contributing/) for development setup, workflow, and guidelines.

## Support

- **[Documentation](https://naas.readthedocs.io/)** - Guides and API reference
- **[Issues](https://github.com/lykinsbd/naas/issues)** - Bug reports and feature requests
- **[Discussions](https://github.com/lykinsbd/naas/discussions)** - Questions and community support

## License

MIT License - see [LICENSE](LICENSE) file for details

---

Built with [Netmiko](https://github.com/ktbyers/netmiko) by Kirk Byers
