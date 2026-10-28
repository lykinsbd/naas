# naas

**Netmiko As A Service** — the core REST API server for [NAAS](https://github.com/lykinsbd/naas).

NAAS provides a production-ready REST API for [Netmiko](https://github.com/ktbyers/netmiko), enabling network automation through HTTP instead of SSH. Run commands on network devices, manage configurations, and integrate with existing tools — all through a simple API backed by an asynchronous job queue.

This package is the server component. For the Python client library see [`naas-client`](../naas-client), and for the MCP server see [`naas-mcp`](../naas-mcp).

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

## Documentation

- 📖 [Full documentation](https://naas.readthedocs.io/)
- 🚀 [Installation guide](https://naas.readthedocs.io/en/stable/installation/)
- 📚 [API reference](https://naas.readthedocs.io/en/stable/api-reference/)

See the [repository root README](https://github.com/lykinsbd/naas#readme) for the full project overview, architecture, and contribution guide.

## License

MIT
