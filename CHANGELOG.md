# NAAS 1.1.0rc3 (2026-02-26)

## ✨ Features

- Device IP lockout: after 10 connection failures within 10 minutes, all access to that device is blocked for 10 minutes, preventing credential-spray abuse across multiple users. Also refactors the user lockout to use the same Redis sorted-set sliding-window implementation. ([#2](https://github.com/lykinsbd/naas/issues/2))
- All log output is now structured JSON, making logs parseable by ELK, Splunk, CloudWatch, and other log aggregation tools. Each log line includes `timestamp`, `level`, `logger`, and `message` fields. ([#79](https://github.com/lykinsbd/naas/issues/79))
- Health check endpoint now returns detailed component status including Redis connectivity, queue depth, version, and uptime. Returns `status: degraded` when Redis is unreachable. ([#81](https://github.com/lykinsbd/naas/issues/81))
- OpenAPI spec now includes Basic Auth security scheme, enabling 'Try it out' authentication in Swagger UI at /apidoc. ([#83](https://github.com/lykinsbd/naas/issues/83))
- All API endpoints are now available under the `/v1/` prefix. Legacy unversioned routes (`/send_command`, `/send_config`) remain functional but return `X-API-Deprecated: true` and `X-API-Sunset: 2027-01-01` headers. All responses include `X-API-Version: v1`. ([#84](https://github.com/lykinsbd/naas/issues/84))
- Add structured request validation using Pydantic: IP address format, platform against all supported Netmiko device types, and non-empty command lists. Invalid requests now return 422 with a structured `errors` array instead of a generic 400. ([#85](https://github.com/lykinsbd/naas/issues/85))
- Add pagination for job history with GET /v1/jobs endpoint ([#87](https://github.com/lykinsbd/naas/issues/87))
- Workers now handle SIGTERM gracefully, finishing in-flight jobs before shutdown with configurable timeout ([#94](https://github.com/lykinsbd/naas/issues/94))
- Job result TTLs are now configurable via environment variables: `JOB_TTL_SUCCESS` (default 24h) and `JOB_TTL_FAILED` (default 7 days). Previously both were hardcoded at ~24h. ([#95](https://github.com/lykinsbd/naas/issues/95))
- Circuit breaker pattern prevents repeated connection attempts to failing devices with configurable thresholds and automatic recovery ([#96](https://github.com/lykinsbd/naas/issues/96))
- Add dynamic OpenAPI spec generation via spectree. The spec is served at `/apidoc/openapi.json` and Swagger UI at `/apidoc`, generated automatically from existing Pydantic request/response models. ([#120](https://github.com/lykinsbd/naas/issues/120))
- Add Pydantic validation for `/v1/jobs` query parameters (`page`, `per_page`, `status`). Invalid values now return 422 instead of being silently clamped. ([#122](https://github.com/lykinsbd/naas/issues/122))

## 🐛 Bug Fixes

- Fix auth guard in get_results.py to use explicit raise instead of assert (assert is stripped by python -O) ([#159](https://github.com/lykinsbd/naas/issues/159))
- Fix list_jobs unfiltered path to paginate per-registry instead of fetching all job IDs into memory; fix total_count to use registry.count rather than len of fetched IDs ([#160](https://github.com/lykinsbd/naas/issues/160))
- Fix bare except Exception in healthcheck.py to catch redis.exceptions.RedisError specifically ([#163](https://github.com/lykinsbd/naas/issues/163))
- Fix module-level Redis client in netmiko_lib.py initialised at import time; now lazily initialised on first use in circuit_breaker.py ([#164](https://github.com/lykinsbd/naas/issues/164))
- Failed jobs now include error detail in the API response. Previously `GET /v1/send_command/{job_id}` returned no error information when a job had status `failed`.

## 📚 Documentation

- Add MkDocs documentation site with Material theme and Read the Docs configuration ([#76](https://github.com/lykinsbd/naas/issues/76))
- Fix command examples in CONTRIBUTING.md, docs/testing.md, and docs/COVERAGE.md to use `uv run` prefix for plug-and-play usage without virtualenv activation ([#124](https://github.com/lykinsbd/naas/issues/124))
- Add v1.1 release notes with migration guide. Update API usage docs with GET /v1/jobs, X-Request-ID tracing, device_type deprecation notice, and 422 error shapes. Fix stale healthcheck response examples. Add Observability, Reliability, and Environment Variables reference pages. ([#135](https://github.com/lykinsbd/naas/issues/135))
- Fix security.md to remove phantom TLS_MIN_VERSION and TLS_CIPHERS environment variables. Document actual TLS behavior: hardcoded secure defaults (TLS 1.2+, HIGH cipher suite) configured in Gunicorn. ([#145](https://github.com/lykinsbd/naas/issues/145))
- Add architecture overview page with Mermaid diagrams covering system components, request lifecycle, async model rationale, and horizontal scaling. ([#146](https://github.com/lykinsbd/naas/issues/146))
- Split CONTRIBUTING.md into a short contributor entry point and a full Development Guide reference page. ([#147](https://github.com/lykinsbd/naas/issues/147))
- Configure Read the Docs to build the develop branch, making bleeding-edge documentation available at naas.readthedocs.io/en/develop/. ([#150](https://github.com/lykinsbd/naas/issues/150))
- Document requirement that all merges to main must go through pull requests
- Fix license section to reference existing MIT license file
- Streamline README for clarity and conciseness
- Update README with Read the Docs links

## 🧪 Testing & CI/CD

- Add cisshgo mock SSH device container to integration test suite. Tests now cover full API→worker→SSH→device path including happy path, auth failure, device lockout, circuit breaker, and error handling scenarios. ([#74](https://github.com/lykinsbd/naas/issues/74))

## 🔧 Internal Changes

- [#80](https://github.com/lykinsbd/naas/issues/80), [#107](https://github.com/lykinsbd/naas/issues/107), [#128](https://github.com/lykinsbd/naas/issues/128), [#154](https://github.com/lykinsbd/naas/issues/154), [#161](https://github.com/lykinsbd/naas/issues/161), [#162](https://github.com/lykinsbd/naas/issues/162)

# Changelog

All notable changes to NAAS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-

- towncrier release notes start -->

# NAAS 1.0.1 (2026-02-24)

## ✨ Features

- Add non-blocking Vale prose linting for changelog fragments. ([#73](https://github.com/lykinsbd/naas/issues/73))

## 🐛 Bug Fixes

- Fix changelog cleanup to remove old pre-releases. ([#72](https://github.com/lykinsbd/naas/issues/72))

## 📚 Documentation

- Restructure README for user-first information architecture with deployment instructions prioritized over development content ([#104](https://github.com/lykinsbd/naas/issues/104))
- Restructure README for user-first information architecture ([#106](https://github.com/lykinsbd/naas/pull/106))

## 🔧 Internal Changes

- [#70](https://github.com/lykinsbd/naas/issues/70), [#71](https://github.com/lykinsbd/naas/issues/71)

## NAAS 1.0.0rc2 (2026-02-23)

### ⚠️ Deprecations

- Rename `device_type` parameter to `platform` to match Netmiko naming convention (backward compatibility maintained in v1.x) ([#25](https://github.com/lykinsbd/naas/issues/25))

### ✨ Features

- Migrate from Docker Swarm to Docker Compose for simpler deployment and better developer experience ([#29](https://github.com/lykinsbd/naas/issues/29))

### 🐛 Bug Fixes

- Fix changelog cleanup to remove old pre-releases. ([#72](https://github.com/lykinsbd/naas/issues/72))

### 📚 Documentation

- Add comprehensive user documentation including quick start guide, API usage examples, troubleshooting guide, and security best practices ([#3](https://github.com/lykinsbd/naas/issues/3))

### 🧪 Testing & CI/CD

- Implement comprehensive CI/CD pipeline with GitHub Actions including automated testing, linting, and Docker builds ([#34](https://github.com/lykinsbd/naas/issues/34))
- Achieve 100% test coverage with comprehensive unit, integration, and contract tests ([#47](https://github.com/lykinsbd/naas/issues/47))

### 🔧 Internal Changes

- [#27](https://github.com/lykinsbd/naas/issues/27), [#60](https://github.com/lykinsbd/naas/issues/60), [#65](https://github.com/lykinsbd/naas/issues/65), [#68](https://github.com/lykinsbd/naas/issues/68), [#70](https://github.com/lykinsbd/naas/issues/70), [#71](https://github.com/lykinsbd/naas/issues/71)
