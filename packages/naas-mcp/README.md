# mcp-server-naas

[MCP](https://modelcontextprotocol.io/) server for [NAAS](https://github.com/lykinsbd/naas) (Netmiko As A Service) — AI-assisted network operations.

Lets AI assistants like Claude, Cursor, and VS Code Copilot send commands to network devices, push configurations, and monitor jobs through the NAAS REST API.

## Install

```bash
pip install mcp-server-naas
```

## Quick Start

```bash
export NAAS_MCP_API_URL=https://naas.example.com
export NAAS_MCP_API_KEY=your-jwt-api-key
naas-mcp
```

## Client Configuration

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "naas": {
      "command": "naas-mcp",
      "env": {
        "NAAS_MCP_API_URL": "https://naas.example.com",
        "NAAS_MCP_API_KEY": "your-jwt-api-key"
      }
    }
  }
}
```

### Cursor

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "naas": {
      "command": "naas-mcp",
      "env": {
        "NAAS_MCP_API_URL": "https://naas.example.com",
        "NAAS_MCP_API_KEY": "your-jwt-api-key"
      }
    }
  }
}
```

### VS Code (Copilot)

`.vscode/mcp.json`:

```json
{
  "servers": {
    "naas": {
      "type": "stdio",
      "command": "naas-mcp",
      "env": {
        "NAAS_MCP_API_URL": "https://naas.example.com",
        "NAAS_MCP_API_KEY": "your-jwt-api-key"
      }
    }
  }
}
```

### Kiro CLI

```bash
kiro-cli mcp add --name naas --command naas-mcp --env NAAS_MCP_API_URL=https://naas.example.com --env NAAS_MCP_API_KEY=your-jwt-api-key
```

Or add to `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "naas": {
      "command": "naas-mcp",
      "env": {
        "NAAS_MCP_API_URL": "https://naas.example.com",
        "NAAS_MCP_API_KEY": "your-jwt-api-key"
      }
    }
  }
}
```

## What You Can Ask

Once connected, your AI assistant can:

- *"Show me the running config on switch-core-01"* → `send_command`
- *"Set the hostname to ROUTER-01 on 10.0.0.1 and save"* → `send_config`
- *"What jobs are running right now?"* → `list_jobs`
- *"Cancel job abc-123"* → `cancel_job`
- *"Is the NAAS API healthy?"* → reads `naas://health` resource

## Tools

| Tool | Description |
|------|-------------|
| `send_command` | Send show/read commands to a device, wait for results |
| `send_config` | Push config commands to a device, wait for results |
| `get_job_result` | Get result of a previously submitted job |
| `cancel_job` | Cancel a queued or running job |
| `list_jobs` | List jobs with optional status filtering |

## Resources

| URI | Description |
|-----|-------------|
| `naas://health` | API health status, version, uptime, worker count |
| `naas://contexts` | Available routing contexts |
| `naas://jobs/failed` | Jobs in the failed registry |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NAAS_MCP_API_URL` | `http://localhost:8080` | NAAS API base URL |
| `NAAS_MCP_API_KEY` | *(none)* | API key (JWT) for Bearer auth |
| `NAAS_MCP_TIMEOUT` | `30` | HTTP timeout in seconds |
| `NAAS_MCP_JOB_POLL_INTERVAL` | `2` | Seconds between job polls |
| `NAAS_MCP_JOB_TIMEOUT` | `300` | Max seconds to wait for job |

## Security

The MCP server is a thin client — it authenticates to the NAAS API with an API key. All RBAC, context authorization, and audit logging are enforced by the API. Device credentials are passed through from the AI's tool call and are never stored by the MCP server.

Create an API key with the appropriate scope:

```bash
naas api-keys create --role operator --contexts default
```

## Development

```bash
git clone https://github.com/lykinsbd/naas.git
cd naas

# Install with dev dependencies
uv sync --package mcp-server-naas --extra dev

# Run unit tests (23 tests, 100% coverage)
uv run --package mcp-server-naas pytest packages/naas-mcp/tests --ignore=packages/naas-mcp/tests/integration

# Run integration tests (requires docker-compose stack)
uv run --package mcp-server-naas pytest packages/naas-mcp/tests/integration -v

# Lint
uv run ruff check --config packages/naas-mcp/pyproject.toml packages/naas-mcp/
```

## License

MIT
