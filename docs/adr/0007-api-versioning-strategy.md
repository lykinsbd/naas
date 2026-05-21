# 7. API Versioning Strategy

Date: 2026-04-07

## Status

Accepted

## Context

NAAS v2.0 introduced breaking changes to the API contract: removed `ip` and `device_type` fields, added mandatory authentication (RBAC, context authorization), and added new endpoints (API key management). These changes were initially applied directly to `/v1/` routes, violating the v1 contract for existing clients.

We needed a strategy to:

1. Honor the original v1 contract for existing clients
2. Introduce the v2 contract with breaking changes
3. Provide a clear migration path with deprecation signals

## Decision

Use **path-based API versioning** where the URL prefix (`/v1/`, `/v2/`) represents the API contract version:

- `/v1/` routes preserve the original contract (deprecated, removed in v3.0)
- `/v2/` routes implement the new contract with all breaking changes
- Both versions share the same resource classes with version-aware behavior
- Deprecation signaled via standard HTTP headers (RFC 8594)

Version-aware behavior is implemented via a `is_v2_request()` helper checked in decorators, not by duplicating resource classes.

> **Exception:** `/healthcheck` (unversioned) is a permanent operational
> endpoint and not subject to the deprecation policy described here. See
> [ADR 0012](0012-unversioned-health-endpoint.md). The versioned forms
> `/v1/healthcheck` and `/v2/healthcheck` follow the standard policy.

## Consequences

### Positive

- Existing clients continue working on `/v1/` without changes
- Clear migration path with deprecation headers and sunset date
- Single codebase — no resource class duplication
- Path version has real semantic meaning (contract version, not cosmetic)

### Negative

- Every decorator/validator that behaves differently per version must check `is_v2_request()`
- New features must decide whether to be v2-only or available on both versions
- `/v1/` routes must be maintained until v3.0

### Conventions

- New endpoints are registered under `/v2/` only unless backward compatibility is required
- `/v2/` routes use hyphenated delimiters (`send-command`), `/v1/` keeps underscores
- The API path version tracks the contract, not the software release version
