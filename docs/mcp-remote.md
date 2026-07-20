# Remote MCP Server (HTTP Transport)

The NAAS MCP server supports **streamable-http** transport, allowing AI assistants to connect over the network instead of requiring a local stdio process. This enables shared, centralized MCP deployments where multiple users and AI clients connect to a single server instance.

> For local stdio-based setup (e.g., Claude Desktop, Cursor), see [mcp-server.md](mcp-server.md).

## Why remote?

- **Shared infrastructure** — one MCP server serves your entire team
- **No local install** — AI clients connect via HTTP, no Python or packages needed locally
- **Centralized auth** — NAAS API keys (JWT) authenticate at the MCP layer with full RBAC
- **Container-ready** — deploy alongside NAAS API in Docker or Kubernetes

## Prerequisites

1. NAAS API running and accessible (e.g., `http://naas-api:8080`)
2. A NAAS API key (JWT) created via `/v2/api-keys` with appropriate role (`admin`, `operator`, or `viewer`)
3. Docker (for containerized deployment) or Python 3.11+ with `uv` (for bare metal)

## Starting the server

### Docker (recommended)

```bash
# From the repo root
docker compose -f docker-compose.mcp.yml up -d

# Or build and run standalone
docker build -f packages/naas-mcp/Dockerfile -t naas-mcp .
docker run -p 8081:8081 \
  -e NAAS_MCP_TRANSPORT=streamable-http \
  -e NAAS_MCP_PORT=8081 \
  -e NAAS_MCP_API_URL=http://naas-api:8080 \
  -e NAAS_JWT_SECRET=your-jwt-secret \
  naas-mcp
```

### Bare metal

```bash
# Install the package
uv pip install mcp-server-naas

# Run with HTTP transport
naas-mcp --transport streamable-http --port 8081
```

Set required environment variables before starting:

```bash
export NAAS_MCP_API_URL=http://localhost:8080
export NAAS_JWT_SECRET=your-jwt-secret
```

## Connecting AI clients

The remote MCP server listens at:

```
http://<host>:8081/mcp
```

Clients authenticate with a **Bearer token** — the same NAAS JWT API key used for direct API access.

### Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "naas": {
      "type": "streamable-http",
      "url": "http://localhost:8081/mcp",
      "headers": {
        "Authorization": "Bearer <your-naas-api-key>"
      }
    }
  }
}
```

### Generic MCP client

Any MCP client supporting streamable-http transport can connect by providing:

- **URL**: `http://<host>:8081/mcp`
- **Header**: `Authorization: Bearer <your-naas-api-key>`

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAAS_MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `streamable-http` |
| `NAAS_MCP_PORT` | `8081` | HTTP listen port (streamable-http only) |
| `NAAS_MCP_HOST` | `0.0.0.0` | HTTP bind address |
| `NAAS_MCP_API_URL` | `http://localhost:8080` | NAAS API base URL |
| `NAAS_JWT_SECRET` | — | JWT secret for validating Bearer tokens |
| `NAAS_MCP_REDIS_URL` | — | Redis URL for session/state (optional) |
| `NAAS_MCP_LOG_LEVEL` | `info` | Logging level |

## Authentication & RBAC

The MCP server validates Bearer tokens using the same `NAAS_JWT_SECRET` as the NAAS API. Token roles map to MCP tool access:

| Role | Access |
|------|--------|
| `admin` | All tools (send-command, send-config, manage jobs) |
| `operator` | send-command, send-config, list/cancel own jobs |
| `viewer` | Read-only tools (show jobs, device info) |

No separate credentials needed — if you have a NAAS API key, it works for MCP too.

## Example: end-to-end

```bash
# 1. Create an API key (via NAAS API)
curl -X POST https://naas.example.com/v2/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "mcp-operator", "role": "operator"}'
# Response: {"api_key": "eyJhbG..."}

# 2. Start the MCP server
docker compose -f docker-compose.mcp.yml up -d

# 3. Configure your AI client with the returned api_key as Bearer token
# 4. The AI assistant can now run network commands through NAAS
```

## Health check

```bash
curl http://localhost:8081/health
```

Returns `200 OK` when the server is ready.
