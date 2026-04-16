# MCP Server

`mcp-server-naas` is an [MCP](https://modelcontextprotocol.io/) server that exposes NAAS operations as discoverable tools and resources for AI assistants like Claude, Cursor, and ChatGPT.

Built with [FastMCP 3.0](https://gofastmcp.com/), it translates MCP tool calls into NAAS API requests via the `naas-client` Python SDK. All auth, RBAC, context authorization, and audit logging still apply — the MCP server is a thin client, not a bypass.

## Installation

```bash
pip install mcp-server-naas
```

Or with `uv`:

```bash
uv pip install mcp-server-naas
```

## Architecture

```
AI Assistant (Claude / Cursor / ChatGPT)
    │
    │ MCP Protocol (JSON-RPC 2.0 over stdio)
    ▼
mcp-server-naas (FastMCP 3.0)
    │
    │ AsyncNaasClient (httpx)
    ▼
NAAS REST API (/v2/ routes)
    │
    │ RQ + Redis
    ▼
Workers → Netmiko → Network Devices
```

The MCP server never connects to devices directly. It authenticates to the NAAS API using an API key, and all operations go through the standard job queue with full RBAC and audit logging.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NAAS_MCP_API_URL` | `http://localhost:8080` | NAAS API base URL |
| `NAAS_MCP_API_KEY` | *(none)* | API key (JWT) for Bearer auth |
| `NAAS_MCP_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `NAAS_MCP_JOB_POLL_INTERVAL` | `2` | Seconds between job status polls |
| `NAAS_MCP_JOB_TIMEOUT` | `300` | Max seconds to wait for job completion |

## Client Setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Add to `.cursor/mcp.json` in your project root:

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

Add to `.vscode/mcp.json`:

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

## Tools

Tools are actions the AI can invoke. Each tool submits a request to the NAAS API and returns the result.

### send_command

Send show/read commands to a network device and wait for results.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `host` | string | ✅ | Device hostname or IP |
| `platform` | string | ✅ | Netmiko platform (e.g. `cisco_ios`, `arista_eos`) |
| `commands` | list[string] | ✅ | Commands to execute |
| `username` | string | | Device username |
| `password` | string | | Device password |
| `enable` | string | | Enable/privilege password |
| `port` | integer | | SSH port (default 22) |
| `tags` | dict | | Key-value tags for the job |

**Example prompt:** *"Show me the running config on switch-core-01"*

**Example result:**

```json
{
  "job_id": "a1b2c3d4",
  "status": "finished",
  "results": {
    "show running-config": "hostname switch-core-01\n..."
  },
  "error": null,
  "error_code": null
}
```

### send_config

Push configuration commands to a network device and wait for results.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `host` | string | ✅ | Device hostname or IP |
| `platform` | string | ✅ | Netmiko platform |
| `commands` | list[string] | ✅ | Configuration commands |
| `username` | string | | Device username |
| `password` | string | | Device password |
| `enable` | string | | Enable/privilege password |
| `port` | integer | | SSH port (default 22) |
| `commit` | boolean | | Commit on platforms that support it (e.g. Junos) |
| `save_config` | boolean | | Save running config to startup |
| `tags` | dict | | Key-value tags for the job |

**Example prompt:** *"Set the hostname to ROUTER-01 on 10.0.0.1 and save the config"*

### get_job_result

Get the result of a previously submitted job by ID.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | ✅ | Job ID from a previous send_command or send_config |

### cancel_job

Cancel a queued or running job.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | ✅ | Job ID to cancel |

### list_jobs

List jobs with optional filtering and pagination.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | | Page number (default 1) |
| `per_page` | integer | | Results per page (default 20) |
| `status` | string | | Filter: `queued`, `started`, `finished`, `failed` |

## Resources

Resources provide read-only data the AI can access for context.

| URI | Description |
|-----|-------------|
| `naas://health` | API health status (server version, uptime, worker count, queue depth) |
| `naas://contexts` | Available routing contexts and their worker/queue state |
| `naas://jobs/failed` | Jobs in the failed (dead letter) registry |

## Security

- The MCP server authenticates to NAAS using an API key — create one with the appropriate role and context scope:

    ```bash
    naas api-keys create --role operator --contexts default
    ```

- **RBAC is enforced by the API**, not the MCP server. An `operator` key can submit jobs but not manage API keys. A `viewer` key can read results but not submit.
- **Device credentials** are passed through from the AI's tool call. The MCP server does not store credentials.
- **Audit logging** captures every operation with the API key's identity.

## Error Handling

When a tool encounters an error, the MCP server returns it as an error result that the AI can interpret:

- **Job failures** (connection timeout, auth failure, config rejected) — the tool raises the error from `naas-client`, which FastMCP surfaces to the AI with the error message.
- **API errors** (404 not found, 429 rate limited, 403 forbidden) — surfaced as MCP tool errors.
- **Timeouts** — if a job doesn't complete within `NAAS_MCP_JOB_TIMEOUT`, the tool raises a timeout error.

The AI sees structured error information including `error_code` and `error_retryable` fields when available, enabling it to suggest fixes or retry automatically.

## Compatibility

- **Python**: 3.11+
- **NAAS server**: ≥ 2.0
- **MCP protocol**: via FastMCP 3.0 (supports stdio and streamable-http transports)
- **Tested with**: Claude Desktop, Cursor, VS Code Copilot
