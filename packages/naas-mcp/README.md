# mcp-server-naas

MCP server for [NAAS](https://github.com/lykinsbd/naas) (Netmiko As A Service) — AI-assisted network operations.

## Install

```bash
pip install mcp-server-naas
```

## Usage

```bash
export NAAS_MCP_API_URL=http://localhost:8080
export NAAS_MCP_API_KEY=your-api-key
naas-mcp
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NAAS_MCP_API_URL` | `http://localhost:8080` | NAAS API base URL |
| `NAAS_MCP_API_KEY` | (none) | API key for Bearer auth |
| `NAAS_MCP_TIMEOUT` | `30` | HTTP timeout in seconds |
| `NAAS_MCP_JOB_POLL_INTERVAL` | `2` | Seconds between job polls |
| `NAAS_MCP_JOB_TIMEOUT` | `300` | Max seconds to wait for job |
