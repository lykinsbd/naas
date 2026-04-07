# Upgrading to v2.0

## API Version Change

NAAS v2.0 introduces `/v2/` API routes. The `/v1/` routes remain available but are **deprecated** and will be removed in v3.0.

All `/v1/` and legacy unversioned responses include deprecation headers:

```http
X-API-Deprecated: true
Deprecation: true
Sunset: 2027-01-01
Link: </v2/>; rel="successor-version"
```

## Route Changes

| v1 (deprecated) | v2 (new) |
| --- | --- |
| `/v1/send_command` | `/v2/send-command` |
| `/v1/send_config` | `/v2/send-config` |
| `/v1/send_command_structured` | `/v2/send-command-structured` |
| `/v1/send_command/<id>` | `/v2/send-command/<id>` |
| `/v1/send_config/<id>` | `/v2/send-config/<id>` |
| `/v1/send_command_structured/<id>` | `/v2/send-command-structured/<id>` |
| `/v1/jobs` | `/v2/jobs` |
| `/v1/jobs/failed` | `/v2/jobs/failed` |
| `/v1/jobs/<id>` | `/v2/jobs/<id>` |
| `/v1/jobs/<id>/replay` | `/v2/jobs/<id>/replay` |
| `/v1/contexts` | `/v2/contexts` |
| `/v1/healthcheck` | `/v2/healthcheck` |
| *(not available)* | `/v2/api-keys` |
| *(not available)* | `/v2/api-keys/<id>` |
| *(not available)* | `/v2/api-keys/<id>/rotate` |

## Field Changes

| v1 (deprecated) | v2 (required) |
| --- | --- |
| `ip` | `host` |
| `device_type` | `platform` |

- `/v1/` routes accept both old and new field names.
- `/v2/` routes reject `ip` and `device_type` with a 422 error.

## Authentication Changes

| Feature | v1 | v2 |
| --- | --- | --- |
| Basic auth | ✅ (device creds in header) | ✅ |
| API key auth (Bearer JWT) | Accepted but not enforced | ✅ Fully enforced |
| RBAC | Not enforced | ✅ `admin > operator > viewer` |
| Context authorization | Not enforced | ✅ JWT `contexts` claim checked |

## New v2 Features

- **API key management** — `POST/GET/DELETE /v2/api-keys`, `POST /v2/api-keys/<id>/rotate`
- **RBAC** — Role-based access control on all endpoints
- **Context authorization** — Scope API keys to specific routing contexts
- **Webhook HMAC signing** — Optional `webhook_secret` field for payload signing
- **Webhook retry** — Exponential backoff on failed deliveries (5s, 30s, 5min, 30min)
- **Credential encryption** — Device credentials encrypted at rest in Redis
- **Audit logging** — Structured events for auth, RBAC, API keys, and webhooks

## Migration Steps

1. Update all API URLs from `/v1/` to `/v2/` with hyphenated paths
2. Replace `ip` with `host` and `device_type` with `platform` in request payloads
3. If using API keys: ensure JWT claims include correct `role` and `contexts`
4. Monitor for `X-API-Deprecated` headers in responses to find remaining v1 usage

## Timeline

- **v2.0** — `/v1/` routes deprecated, `/v2/` routes available
- **v3.0** — `/v1/` and legacy unversioned routes removed
