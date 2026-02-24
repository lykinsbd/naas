# NAAS - Netmiko As A Service

Welcome to the NAAS documentation! NAAS is a REST API wrapper for [Netmiko](https://github.com/ktbyers/netmiko), enabling network device automation through a simple HTTP interface.

## What is NAAS?

NAAS provides a production-ready API for executing commands and configurations on network devices. It handles:

- **Asynchronous job processing** - Commands run in background workers
- **Multiple device platforms** - Supports all Netmiko-compatible devices (Cisco, Arista, Juniper, etc.)
- **Secure authentication** - HTTPS with TLS and HTTP Basic Auth
- **Job tracking** - Query job status and retrieve results
- **Production features** - Health checks, logging, error handling

## Quick Example

```bash
# Send a command
curl -X POST https://naas.example.com/v1/send_command \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.1",
    "platform": "cisco_ios",
    "commands": ["show version", "show interfaces"]
  }'

# Response
{
  "job_id": "abc123",
  "status": "queued",
  "created_at": "2026-02-23T22:00:00Z"
}

# Get results
curl https://naas.example.com/v1/get_results/abc123 \
  -u admin:password
```

## Features

- ✅ REST API for network device automation
- ✅ Asynchronous job processing with Redis Queue (RQ)
- ✅ Support for 100+ device platforms via Netmiko
- ✅ HTTPS with TLS encryption
- ✅ HTTP Basic Authentication
- ✅ Docker Compose deployment
- ✅ Comprehensive test coverage
- ✅ Production-ready logging and error handling

## Getting Started

- [Quick Start](quickstart.md) - Get NAAS running in 5 minutes
- [API Usage](api-usage.md) - Learn how to use the API
- [Security](security.md) - Secure your deployment

## Project Links

- [GitHub Repository](https://github.com/lykinsbd/naas)
- [Issue Tracker](https://github.com/lykinsbd/naas/issues)
- [Changelog](changelog.md)
