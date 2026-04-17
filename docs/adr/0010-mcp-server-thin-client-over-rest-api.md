# ADR 0010: MCP Server as Thin Client over REST API

* Status: Accepted
* Date: 2026-04-16

## Context and Problem Statement

AI assistants (Claude, ChatGPT, Cursor, Kiro) need a standardized way to discover and invoke NAAS operations. The Model Context Protocol (MCP) provides this standard, but the server could be implemented at different layers — directly against Redis/RQ internals, as a Flask blueprint, or as a standalone client of the existing REST API.

## Decision Drivers

* AI assistants should get the same auth, RBAC, audit logging, and rate limiting as any other consumer
* The MCP server should not become a second API surface that diverges from the REST API
* FastMCP 3.0 is the mature Python framework for MCP servers, with built-in testing support
* The existing `naas-client` async SDK (`AsyncNaasClient`) already wraps the REST API

## Considered Options

* **Option 1**: MCP server embedded in the Flask app as a blueprint
* **Option 2**: Standalone MCP server calling Redis/RQ directly
* **Option 3**: Standalone MCP server as a thin client over the REST API via `naas-client`

## Decision Outcome

Chosen option: **Option 3 — thin client over REST API**, because it reuses the existing API boundary and guarantees all security controls apply without duplication.

### Architecture

```text
AI Assistant (Claude / Cursor / ChatGPT)
    │ MCP Protocol (JSON-RPC 2.0 over stdio)
    ▼
naas-mcp (FastMCP 3.0)
    │ AsyncNaasClient (httpx)
    ▼
NAAS REST API (/v2/ routes)
    │ RQ + Redis
    ▼
Workers → Netmiko → Devices
```

### Key design choices

* **Separate package** (`packages/naas-mcp`, published as `mcp-server-naas`) — independent release cycle, no coupling to server internals
* **Imports from `naas-client`, not `naas`** — same API boundary as any external consumer
* **FastMCP 3.0 lifespan** — `AsyncNaasClient` created on startup, closed on shutdown, injected via `Context`
* **Job polling in tools** — `send_command` and `send_config` submit a job then poll until terminal state, so the AI gets a final result rather than a job ID
* **stdio transport** — default for local AI assistants; streamable-http deferred to future work

### Consequences

* Good: All auth, RBAC, audit logging, rate limiting, and circuit breakers apply automatically
* Good: MCP server can't bypass API controls — it's just another client
* Good: Independent versioning and release from the main server
* Good: FastMCP test client enables in-process testing without network transport
* Bad: Extra network hop (MCP → API → worker) adds latency — acceptable for interactive AI use
* Bad: MCP server cannot expose operations not yet in the REST API — accepted, keeps surfaces aligned

## Pros and Cons of the Options

### Option 1: Embedded Flask blueprint

* Good: No extra network hop, single deployment
* Bad: Couples MCP to Flask lifecycle and release cycle
* Bad: MCP protocol (JSON-RPC over stdio) doesn't fit naturally in a WSGI app
* Bad: Harder to test MCP tools in isolation

### Option 2: Standalone calling Redis/RQ directly

* Good: Lowest latency, no API dependency
* Bad: Bypasses all API security controls (auth, RBAC, audit, rate limiting)
* Bad: Duplicates job submission logic, creates second API surface
* Bad: Tight coupling to internal queue implementation

### Option 3: Thin client over REST API

* Good: Reuses all existing security and observability infrastructure
* Good: Clean separation — MCP server is just another API consumer
* Good: `naas-client` already handles auth, retries, and async
* Bad: Extra hop adds ~10-50ms latency per call — negligible for AI interactions
