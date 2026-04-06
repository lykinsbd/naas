# API Key Authentication

* Status: Proposed
* Date: 2026-04-06

## Context and Problem Statement

NAAS authenticates users via HTTP Basic auth, which serves dual purpose: authenticating
the caller to the API and providing SSH credentials for Netmiko device connections. This
coupling makes it impossible to implement RBAC, audit logging by identity, or
machine-to-machine API access without device credentials.

NAAS needs an API-level authentication mechanism that identifies the caller independently
of device credentials, enabling role-based access control (#102), context-based
authorization (#291), and enhanced audit logging (#100).

## Decision Drivers

* Must coexist with Basic auth (backward compatibility)
* Must support embedded permissions for RBAC and context authorization
* Must minimize per-request latency (avoid unnecessary Redis lookups)
* Must integrate with the secrets backend (ADR 0002) for signing key management
* Must not create a one-way door against future credential vaulting (JWT-only auth
  where NAAS pulls device credentials from the secrets backend)

## Considered Options

* **Option 1:** Opaque API keys (random tokens, hashed in Redis)
* **Option 2:** JWTs with embedded claims (hybrid — long-lived + revocation list)

## Decision Outcome

Chosen option: **Option 2 — JWTs with embedded claims**, because self-contained tokens
eliminate per-request Redis lookups for role/context checks, and the standard format
provides a natural path to RBAC and context authorization via claim inspection.

### Consequences

* Good: RBAC and context authz become simple claim checks, not Redis queries
* Good: Stateless signature verification — auth works even during Redis blips
* Good: Standard format (RFC 7519) with mature library support (PyJWT)
* Good: Clients can decode their own token to inspect permissions
* Good: Forward-compatible with credential vaulting (key_id in `sub` claim is a
  natural lookup key for stored device credentials)
* Bad: Revocation requires a Redis set check (small, fast, but not fully stateless)
* Bad: Slightly more implementation complexity than opaque tokens

## Design

### Token Format

HMAC-SHA256 signed JWT with the following claims:

| Claim | Type | Description |
| --- | --- | --- |
| `sub` | string | Key ID (e.g., `k-1`) — unique identifier for this API key |
| `role` | string | Role: `admin`, `operator`, or `viewer` (prep for RBAC #102) |
| `contexts` | list[str] | Allowed routing contexts, `["*"]` for all (prep for #291) |
| `iat` | int | Issued-at timestamp |
| `exp` | int | Expiration timestamp (default 90 days, 0 for no expiry) |

### Signing

* Algorithm: HS256 (HMAC-SHA256)
* Signing secret: `NAAS_JWT_SECRET` loaded from the secrets backend
* Library: `PyJWT`

### Authentication Flow

```text
Request arrives
  │
  ├─ Authorization: Basic <user:pass>
  │    └─ Existing flow (device creds extracted from header)
  │
  └─ Authorization: Bearer <jwt>
       ├─ Verify signature (local, no Redis)
       ├─ Check expiration
       ├─ Check revocation set in Redis (SISMEMBER, O(1))
       ├─ Extract claims (role, contexts)
       └─ Device credentials from request body (username/password/enable fields)
```

### Device Credentials with JWT Auth

When using JWT authentication, device credentials are provided in the request body:

```json
{
  "host": "192.168.1.1",
  "platform": "cisco_ios",
  "commands": ["show version"],
  "username": "netadmin",
  "password": "secret",
  "enable": "enablepass"
}
```

`username` and `password` are required when using JWT auth. `enable` is optional.
When using Basic auth, these fields are ignored (credentials come from the header).

**Future: credential vaulting.** The `sub` claim (key ID) provides a natural lookup
key for stored device credentials. A future enhancement can make `username`/`password`
optional by falling back to credentials stored in the secrets backend, keyed by
`sub`. This requires no changes to the JWT format or validation flow.

### Key Management Endpoints

| Endpoint | Method | Auth | Description |
| --- | --- | --- | --- |
| `/v1/api-keys` | POST | Admin | Create a new API key (returns JWT once) |
| `/v1/api-keys` | GET | Admin | List keys (metadata only, not tokens) |
| `/v1/api-keys/{key_id}` | DELETE | Admin | Revoke a key (adds to revocation set) |

**Create response** (token shown once):

```json
{
  "key_id": "k-1",
  "token": "eyJhbG...",
  "role": "operator",
  "contexts": ["default", "oob-dc1"],
  "expires_at": "2026-07-04T00:00:00Z"
}
```

### Revocation

* Revoked key IDs stored in a Redis set (`naas:revoked_keys`)
* Checked on every JWT-authenticated request via `SISMEMBER` (O(1))
* Set is small (only revoked keys, not all keys) — negligible overhead
* TTL on set members matches token expiration (auto-cleanup)

### Storage

* **No key table needed** — JWTs are self-contained; only revocation state is stored
* **Key metadata** (for list endpoint): Redis hash `naas:api_keys:{key_id}` with
  `role`, `contexts`, `created_at`, `expires_at`, `created_by`
* **Revocation set**: Redis set `naas:revoked_keys`

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `NAAS_JWT_SECRET` | (required via secrets backend) | HMAC signing secret |
| `API_KEY_DEFAULT_TTL` | `7776000` (90 days) | Default key expiration in seconds |
| `API_KEY_MAX_TTL` | `0` (unlimited) | Maximum allowed TTL, 0 for no limit |

### Backward Compatibility

* Basic auth continues to work unchanged
* API key auth is opt-in — no existing workflows break
* Both auth methods use the same downstream code paths (validation, enqueue, etc.)
* The `role` claim defaults to `admin` until RBAC (#102) is implemented

### Scope for v2.0

* JWT creation, validation, and revocation
* Key management endpoints (create, list, revoke)
* `username`/`password`/`enable` body fields for device credentials
* `PyJWT` added as a core dependency
* Role claim included but not enforced until RBAC (#102)
* Contexts claim included but not enforced until context authz (#291)

## Pros and Cons of the Options

### Option 1: Opaque API keys

* Good: Simple to implement (generate, hash, compare)
* Good: Easy revocation (delete hash from Redis)
* Bad: Every request requires Redis lookup for validation
* Bad: Role and context permissions require additional Redis lookups
* Bad: Custom format, no standard tooling
* Bad: No path to stateless validation

### Option 2: JWTs with embedded claims

* Good: Stateless signature verification (no Redis for auth)
* Good: Embedded claims eliminate role/context lookups
* Good: Standard format, mature library ecosystem
* Good: Forward-compatible with credential vaulting
* Bad: Revocation requires Redis set check (small overhead)
* Bad: More implementation complexity than opaque tokens
* Bad: Token rotation requires reissuing (not just updating Redis)
