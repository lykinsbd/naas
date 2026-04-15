# ADR 0009: Command Authorization Deferred to AAA/TACACS+

* Status: Accepted
* Date: 2026-04-15

## Context and Problem Statement

NAAS proxies arbitrary commands to network devices. A caller with valid RBAC credentials can submit any command — including destructive operations like `reload`, `write erase`, or `format:` — through the REST API. Should NAAS enforce command-level restrictions at the proxy layer?

## Decision Drivers

* NAAS is a transport proxy, not an authorization system
* Network environments already enforce per-user, per-device, per-command authorization via TACACS+/RADIUS at the device layer
* Duplicating authorization policy in two places creates drift risk and operational burden
* Direct SSH access bypasses any proxy-layer filtering, making it an incomplete control

## Considered Options

* **Option 1**: Full command allowlist/denylist per role/context
* **Option 2**: Minimal catastrophic-command denylist (static list: `reload`, `write erase`, etc.)
* **Option 3**: No command filtering — defer to AAA

## Decision Outcome

Chosen option: **Option 3 — defer command authorization to AAA/TACACS+**, because command authorization is a device-layer concern and NAAS should not replicate identity infrastructure that already exists.

### What NAAS provides instead

* **RBAC** — controls who can submit jobs (viewer/operator/admin), not what commands
* **Audit logging** — every command submission is logged with caller identity, device, and timestamp
* **Rate limiting** — per-caller and per-caller-per-device sliding windows prevent abuse
* **Device lockout** — repeated auth failures trigger per-device lockout
* **Circuit breaker** — repeated connection failures open the breaker

### Deployment expectation

Operators deploying NAAS should configure TACACS+ or RADIUS on managed devices. When NAAS connects with a shared service account, that account's TACACS+ profile should restrict commands appropriately. The recommended pattern is per-user credential passthrough (NAAS already supports this) so that device-level AAA applies the caller's own authorization policy.

### Consequences

* Good: Clean separation of concerns — NAAS stays a thin proxy, no policy drift
* Good: No regex maintenance burden or false-positive operational friction
* Good: No false sense of security from an incomplete control (direct SSH bypasses it)
* Bad: No proxy-layer safety net for environments with weak or missing AAA — accepted risk, documented above

## Pros and Cons of the Options

### Option 1: Full allowlist/denylist

* Good: Defense in depth, catches shared service account gap
* Bad: Duplicates TACACS+ policy with drift risk
* Bad: Complex regex maintenance, per-platform command syntax differences
* Bad: Bypassable via direct SSH — incomplete control

### Option 2: Minimal catastrophic-command denylist

* Good: Low complexity, prevents worst-case accidents
* Bad: Low value if AAA is functioning
* Bad: Denylist too aggressive becomes operational friction
* Bad: Still bypassable via direct SSH

### Option 3: No command filtering

* Good: Zero maintenance, no policy drift, clean architecture
* Good: Encourages proper AAA configuration at the device layer
* Bad: No safety net for misconfigured environments
