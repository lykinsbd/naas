# Role-Based Access Control

* Status: Accepted
* Date: 2026-04-06

## Context and Problem Statement

NAAS now supports JWT-based API key authentication (ADR 0003) with a `role` claim
embedded in each token. However, the role is not enforced — all authenticated users
have full access to every endpoint. NAAS needs to restrict actions based on the
caller's role to support least-privilege access for automation and service accounts.

## Decision Drivers

* Must not break existing Basic auth users (backward compatibility)
* Must use the `role` claim already embedded in JWTs (no schema changes)
* Must be simple to reason about (small number of roles, no permission tables)
* Must be easy to extend when context authorization (#291) is added later

## Considered Options

* **Option 1:** Fine-grained permission system (role → permission set → endpoint mapping)
* **Option 2:** Ordered role hierarchy with a `require_role` decorator

## Decision Outcome

Chosen option: **Option 2 — ordered role hierarchy**, because three roles with a
linear hierarchy are sufficient for NAAS's access patterns, and a decorator-based
approach requires no new storage or configuration.

### Consequences

* Good: Zero new infrastructure — roles are already in the JWT, enforcement is a decorator
* Good: Easy to understand — `admin > operator > viewer`, no permission tables
* Good: Basic auth backward compatible — implicitly treated as admin
* Good: Natural extension point for context authorization (#291)
* Bad: Cannot grant a viewer the ability to send commands without promoting to operator
* Bad: Adding a new role requires updating the hierarchy (acceptable at this scale)

## Design

### Roles

| Role | Rank | Description |
| --- | --- | --- |
| `viewer` | 0 | Read-only access to job status and metadata |
| `operator` | 1 | Send commands/config, cancel/replay jobs, plus all viewer permissions |
| `admin` | 2 | Manage API keys, plus all operator permissions |

### Endpoint Permissions

| Endpoint | Method | Minimum Role |
| --- | --- | --- |
| `/v1/healthcheck` | GET | (no auth required) |
| `/v1/contexts` | GET | viewer |
| `/v1/jobs` | GET | viewer |
| `/v1/send_command/{id}` | GET | viewer |
| `/v1/send_config/{id}` | GET | viewer |
| `/v1/send_command_structured/{id}` | GET | viewer |
| `/v1/send_command` | POST | operator |
| `/v1/send_command_structured` | POST | operator |
| `/v1/send_config` | POST | operator |
| `/v1/jobs/{id}` | DELETE | operator |
| `/v1/jobs/{id}/replay` | POST | operator |
| `/v1/jobs/failed` | GET | operator |
| `/v1/api-keys` | POST/GET/DELETE | admin (already gated by `NAAS_ADMIN_SECRET`) |

### Enforcement

A `require_role` decorator applied to resource methods:

```python
ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

def require_role(minimum_role: str):
    """Enforce minimum role for JWT-authenticated requests.

    Basic auth users are implicitly admin (backward compatibility).
    """
```

The decorator checks `g.auth_method`:

* `basic` → pass through (implicit admin, no behavior change)
* `bearer` → compare `g.jwt_claims["role"]` rank against the minimum

Returns 403 Forbidden if the caller's role is insufficient.

### Basic Auth Users

Basic auth users are treated as admin. This preserves full backward compatibility —
no existing workflow is affected by RBAC enforcement. When Basic auth is disabled by
default in v3.0, all users will authenticate via JWT with explicit roles.

### Integration with Context Authorization (#291)

The `require_role` decorator checks *what actions* a user can perform. Context
authorization (#291) will check *which devices/contexts* they can target. These are
orthogonal and compose naturally:

```python
@require_role("operator")  # Can you send commands at all?
def post(self):
    # Context authz checks g.jwt_claims["contexts"] against the request's context
    validate_context_access(request.json["context"], g.jwt_claims["contexts"])
```

### Scope for v2.0

* `require_role` decorator in `naas/library/auth.py`
* Applied to all resource methods
* Unit tests for each role × endpoint combination
* No changes to JWT format, API key management, or request models
