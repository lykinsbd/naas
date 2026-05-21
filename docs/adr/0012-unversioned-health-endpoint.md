# ADR 0012

## `/healthcheck` as a permanent unversioned operational endpoint

* Status: Accepted
* Date: 2026-05-21

## Context and Problem Statement

When ADR 0007 introduced `/v1/` and `/v2/` API versioning, NAAS retained
several unversioned routes as deprecated aliases of their `/v1/` counterparts:
`/send_command`, `/send_config`, `/send_command/<job_id>`, `/send_config/<job_id>`,
and `/healthcheck`. All five were planned for removal in v3.0 alongside `/v1/`
itself.

`/healthcheck` is qualitatively different from the others. The data-plane
aliases (`/send_command`, `/send_config`) are pure backward compatibility for
clients that hardcoded URLs before path-versioning was introduced. Their
contract changed in v2.0 (field renames, hyphenated paths, mandatory auth) and
removing them in v3.0 forces those clients to migrate to `/v2/` — which is the
desired outcome.

`/healthcheck`, on the other hand, isn't really an API contract endpoint. It's
a service-availability probe consumed by infrastructure tooling, not by client
code. It is currently used by:

* `k8s/api/deployment.yaml` — Kubernetes liveness and readiness probes
* `charts/naas/templates/api-deployment.yaml` — Helm chart probes
* `packages/naas/Dockerfile` — Docker `HEALTHCHECK` directive
* `packages/naas/tests/integration/docker-compose.test.yml` — integration test
  service health gate

There is no semantic difference between `/v1/healthcheck` and `/v2/healthcheck`
— both call the same `HealthCheck` resource and return the same component-status
payload. The only contract a healthcheck has is "200 OK = service alive."

Removing `/healthcheck` in v3.0 would force every operator to coordinate three
changes on upgrade — application bump, manifest path change, redeploy — for an
endpoint with no contract-versioning benefit. The same is true for the Dockerfile
and Helm chart shipped by NAAS itself: they would need a coordinated rev to
avoid breaking on the v3.0 image.

## Decision Drivers

* The healthcheck endpoint is a universal infrastructure convention, not an API
  contract
* `/healthcheck`, `/v1/healthcheck`, and `/v2/healthcheck` are functionally
  identical — versioning communicates a contract change that doesn't exist
* Removing `/healthcheck` would break NAAS's own K8s manifests, Helm chart, and
  Dockerfile on v3.0 upgrade with no offsetting benefit
* Industry convention (AWS ELB targets, GCP probes, GitHub, Stripe, RFC-style
  `/livez`/`/readyz`) treats health endpoints as unversioned
* Operators consuming NAAS expect to write `/healthcheck` in their probes, not a
  vendor-specific versioned path

## Considered Options

* **Option A — Keep `/healthcheck` deprecated, remove in v3.0** (the original
  ADR 0007 stance)
* **Option B — Un-deprecate `/healthcheck` as a permanent operational endpoint;
  keep `/v1/healthcheck` deprecated** (chosen)
* **Option C — Add new `/livez`/`/readyz` endpoints, deprecate `/healthcheck`,
  and migrate** (a larger restructure, deferred)

## Decision Outcome

Chosen option: **Option B — Un-deprecate `/healthcheck` as a permanent
operational endpoint. Keep `/v1/healthcheck` deprecated alongside other `/v1/`
routes.**

This carves a narrow exception in the ADR 0007 deprecation policy: unversioned
operational endpoints (currently just `/healthcheck`) are permanent, while
unversioned **data-plane** aliases (`/send_command`, `/send_config`) remain
deprecated and are removed in v3.0 as planned.

`/v1/healthcheck` is treated like any other `/v1/` route — deprecated and
removed in v3.0. Operators who want a versioned form should use `/v2/healthcheck`.
Operators who want the universal infrastructure-probe convention use
`/healthcheck`.

### Consequences

* Good: NAAS's own K8s manifests, Helm chart, and Dockerfile do not need
  coordinated changes for the v3.0 upgrade — `/healthcheck` continues to work
  exactly as it did
* Good: External operators don't have to write a NAAS-specific versioned probe
  path — `/healthcheck` matches the industry convention
* Good: `/v1/healthcheck` is still removable in v3.0, so no regression on the
  versioning policy for clients who explicitly opted into v1
* Bad: Adds a documented exception to "everything unversioned is deprecated."
  This is a small cost paid in ADR documentation and in the deprecation banner
  text
* Bad: Walks back a public commitment made in v2.0 deprecation messaging. Since
  v2.0 is recent and the un-deprecation is more permissive (clients aren't
  forced to migrate something they expected to lose), the migration impact is
  zero — but it's still a reversal worth being explicit about

## Pros and Cons of the Options

### Option A — Keep deprecated, remove in v3.0

* Good: Maximum consistency — every unversioned route gone, single mental model
* Bad: NAAS's own infrastructure (manifests, Helm, Dockerfile) must coordinate
  a `/healthcheck` → `/v2/healthcheck` change with v3.0, or break on upgrade
* Bad: External operators bear the same cost across every NAAS deployment they
  run, for no contract benefit
* Bad: Diverges from universal infrastructure probe convention

### Option B — Un-deprecate `/healthcheck` (chosen)

* Good: Aligns with K8s, Docker, and cloud-provider conventions
* Good: No coordination cost on v3.0 upgrade — operators leave probes alone
* Good: `/v1/healthcheck` still removed, so the versioning policy for clients
  is preserved
* Bad: One documented exception to the unversioned-is-deprecated rule

### Option C — Add `/livez` / `/readyz`, migrate from `/healthcheck`

* Good: Aligns with the [Kubernetes API conventions](https://kubernetes.io/docs/reference/using-api/health-checks/)
  for separating liveness and readiness
* Bad: Substantially larger scope — new endpoints, new semantics (liveness vs.
  readiness vs. startup), migration plan
* Bad: Doesn't solve the immediate question of what to do with `/healthcheck`
  before v3.0
* Deferred. If/when NAAS wants distinct liveness and readiness signals, that is
  a separate enhancement evaluated against this baseline

## Implementation Notes

* `/healthcheck` is removed from `_DEPRECATED_PREFIXES` in
  `packages/naas/naas/app.py`. `/v1/healthcheck` remains via the `/v1/` prefix
  match
* The deprecation banners in `README.md`, `docs/index.md`, `docs/quickstart.md`,
  and `docs/api-usage.md` no longer list `/healthcheck` among the deprecated
  unversioned aliases
* The migration table in `docs/upgrading.md` calls out `/healthcheck` as a
  permanent operational endpoint, distinguishing it from `/v1/healthcheck`
* `packages/naas/tests/unit/test_resources_api.py` tests the contract:
  `/healthcheck` MUST NOT emit deprecation headers, `/v1/healthcheck` MUST

## Related

* [ADR 0007 — API versioning strategy](0007-api-versioning-strategy.md) —
  establishes the path-versioning approach this ADR carves an exception from
* Issue #512 — implements this decision
* Issue #507 — tracks v3.0 removal of `/v1/` routes (still includes
  `/v1/healthcheck`)
