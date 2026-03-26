# Changelog

All notable changes to NAAS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# NAAS 1.4.0b1 (2026-03-26)

## ✨ Features

- Add CONNECTION_POOL_EXCLUDE environment variable to exclude specific device IPs or platforms from connection pooling. ([#187](https://github.com/lykinsbd/naas/issues/187))
- Add TTP structured output support to /v1/send_command_structured endpoint via ttp_template parameter. Mutually exclusive with textfsm_template. ([#246](https://github.com/lykinsbd/naas/issues/246))
- Add host field accepting IP addresses and hostnames. Deprecate ip field (still works, will be removed in v2.0). ([#270](https://github.com/lykinsbd/naas/issues/270))
- Enqueue response now includes queue_position, enqueued_at, and timeout fields. ([#271](https://github.com/lykinsbd/naas/issues/271))
- Add webhook_url field to all job submission endpoints. When set, NAAS POSTs a job completion notification (job_id, status, timestamps — never results or credentials) to the URL when the job finishes. ([#275](https://github.com/lykinsbd/naas/issues/275))
- Add optional tags field (dict[str,str]) to all enqueue requests. Tags stored in job metadata, returned in job results and list_jobs. Filter jobs by tag with ?tag=key:value. ([#276](https://github.com/lykinsbd/naas/issues/276))
- Add MAX_QUEUE_DEPTH config to limit queue depth and return 503 when exceeded. ([#279](https://github.com/lykinsbd/naas/issues/279))
- Add X-Idempotency-Key header support. Repeat requests with the same key return the original job_id instead of enqueuing a new job. ([#280](https://github.com/lykinsbd/naas/issues/280))
- Add dead letter queue endpoints: GET /v1/jobs/failed lists failed jobs (credentials never exposed), POST /v1/jobs/{job_id}/replay re-enqueues with caller's credentials. Includes FAILED_JOB_MAX_RETAIN config and naas_failed_jobs_total Prometheus gauge. ([#281](https://github.com/lykinsbd/naas/issues/281))
- Add job reaper background thread that detects orphaned jobs from dead workers and moves them to FailedJobRegistry. Uses distributed Redis lock to ensure only one reaper runs per cycle. ([#282](https://github.com/lykinsbd/naas/issues/282))
- Add global Redis error handler returning 503 with Retry-After header instead of unhandled 500. ([#283](https://github.com/lykinsbd/naas/issues/283))
- Add server-side job deduplication. Duplicate in-flight jobs (same host+platform+commands+user) return the existing job_id with deduplicated=true. Dedup keys cleared automatically via RQ callbacks on job completion/failure. ([#285](https://github.com/lykinsbd/naas/issues/285))
- Add context-aware job routing for multi-VRF and multi-segment environments. Workers declare contexts via WORKER_CONTEXTS; callers specify context in requests. Includes GET /v1/contexts endpoint and comprehensive documentation. ([#290](https://github.com/lykinsbd/naas/issues/290))
- Add conn_timeout field to all job submission endpoints to control TCP connection timeout (default 10s). Useful for fast failure detection on unreachable hosts or tuning for high-latency links. ([#304](https://github.com/lykinsbd/naas/issues/304))

## 🐛 Bug Fixes

- Fix Dockerfile hardcoded python3.11 path to use ARG PYTHON_VERSION, enabling base image upgrades. ([#261](https://github.com/lykinsbd/naas/issues/261))

## 📚 Documentation

- Add Postman collection and OpenAPI spec as release artifacts. Document API client import instructions for Postman, Insomnia, and Bruno. ([#92](https://github.com/lykinsbd/naas/issues/92))
- Establish ADR process using MADR format. Add docs/adr/ directory with template and first ADR for Python client library integration strategy. ([#265](https://github.com/lykinsbd/naas/issues/265))
- Fix MD060 table column style violations across documentation files.

## 🧪 Testing & CI/CD

- Add Python 3.12, 3.13, and 3.14 to CI test matrix. Bump Docker default base image to python:3.14-slim. ([#263](https://github.com/lykinsbd/naas/issues/263))
- Expand integration tests to cover v1.4 features: host field, deprecated ip field, enqueue response metadata, structured output (TextFSM/TTP), and context routing with multiple workers. ([#293](https://github.com/lykinsbd/naas/issues/293))
- Add Docker BuildKit GHA layer caching to integration test builds, reducing rebuild time on cache hits. ([#302](https://github.com/lykinsbd/naas/issues/302))
- Run integration tests on Python 3.14 only — the Docker container always uses 3.14 regardless of matrix version, so multi-version integration testing added no coverage value. ([#303](https://github.com/lykinsbd/naas/issues/303))
- Reduce k8s CI test time by patching GUNICORN_WORKERS=2 on the API deployment and reducing rollout timeouts from 180s to 90s. ([#308](https://github.com/lykinsbd/naas/issues/308))

## 🔧 Internal Changes

- Remove black dependency, superseded by ruff format. ([#258](https://github.com/lykinsbd/naas/issues/258))
- Use RELEASE_TOKEN in finalize-release workflow to trigger CI checks on auto-created PRs

# NAAS 1.3.1 (2026-03-06)

## 📚 Documentation

- Standardize bash syntax highlighting in kubernetes.md code blocks. ([#201](https://github.com/lykinsbd/naas/issues/201))
- Clarify worker concurrency vs connection pooling in kubernetes.md. ([#202](https://github.com/lykinsbd/naas/issues/202))
- Add response schema documentation to HealthCheck.get() docstring. ([#203](https://github.com/lykinsbd/naas/issues/203))
- Add v1.2 and v1.3 release notes and fix v1.0.0 changelog entry.

# NAAS 1.3.0rc2 (2026-03-04)

## 💥 Breaking Changes

- Replace delay_factor parameter with read_timeout (float, seconds) in send_command and send_config endpoints ([#216](https://github.com/lykinsbd/naas/issues/216))

## 🔒 Security

- Run API and worker containers as non-root user (UID 1000) with NET_BIND_SERVICE capability for port 443 ([#198](https://github.com/lykinsbd/naas/issues/198))
- Set readOnlyRootFilesystem on API and worker containers; pre-compile Python bytecode in Dockerfile ([#206](https://github.com/lykinsbd/naas/issues/206))

## ✨ Features

- Add /v1/send_command_structured endpoint with TextFSM parsing via ntc-templates or custom templates ([#219](https://github.com/lykinsbd/naas/issues/219))
- Add optional expect_string parameter to send_command for custom prompt matching ([#220](https://github.com/lykinsbd/naas/issues/220))
- Add platform autodetect via SSHDetect for discovery workflows and heterogeneous environments ([#222](https://github.com/lykinsbd/naas/issues/222))

## 🐛 Bug Fixes

- Detect config errors via `error_pattern` in `send_config_set`, returning error string instead of succeeding silently ([#217](https://github.com/lykinsbd/naas/issues/217))
- Call find_prompt() after connection pool hit to verify clean CLI state before issuing commands ([#218](https://github.com/lykinsbd/naas/issues/218))
- Use `setnx` for `naas_cred_salt` so API restarts do not invalidate existing connection pool keys and in-flight job auth ([#223](https://github.com/lykinsbd/naas/issues/223))
- Pass Redis connection explicitly to `tacacs_auth_lockout` and `device_lockout`, eliminating per-request TCP connection overhead ([#224](https://github.com/lykinsbd/naas/issues/224))
- Set explicit `job_timeout` on enqueue to prevent hung workers holding for RQ's 180s default ([#226](https://github.com/lykinsbd/naas/issues/226))
- Call `redis.ping()` at startup to fail fast if Redis is unavailable ([#227](https://github.com/lykinsbd/naas/issues/227))

## 📚 Documentation

- Add comprehensive documentation for v1.3.0 features: job cancellation, connection pooling, Prometheus metrics, audit events, expect_string parameter, and troubleshooting guides

## 🔧 Internal Changes

- Explicitly set fast_cli=True on ConnectHandler for consistent throughput across all platforms ([#221](https://github.com/lykinsbd/naas/issues/221))
- Use Job.fetch_many() in ListJobs to batch-fetch job details in a single Redis pipeline call ([#225](https://github.com/lykinsbd/naas/issues/225))
- Pass Job object directly to `job_locker` to avoid redundant Redis fetch after enqueue ([#228](https://github.com/lykinsbd/naas/issues/228))
- Add comment to `worker_cache` documenting per-process global state assumption ([#229](https://github.com/lykinsbd/naas/issues/229))
- Ignore codecov.io badge URLs in link-check to prevent flaky CI failures ([#234](https://github.com/lykinsbd/naas/issues/234))
- Share Docker image between build.yml and k8s-tests via artifact to eliminate duplicate builds ([#240](https://github.com/lykinsbd/naas/issues/240))
- Automate release workflow: auto-create PR from main to develop, auto-bump develop to next alpha version after release
- Improve code quality: add docstrings, avoid mutable dict mutations, replace bare except with specific exceptions, eliminate type ignore comments
- Replace shell scripts with Python for changelog cleanup, add comprehensive unit tests, fix bugs in cleanup_released_fragments and cleanup_changelog scripts

# NAAS 1.2.0 (2026-03-02)

## ✨ Features

- Add connection pooling for persistent SSH device connections, reducing VTY session overhead on network devices ([#57](https://github.com/lykinsbd/naas/issues/57))
- Add Prometheus metrics endpoint at `/metrics` exposing request counts, latency, queue depth, worker count, and job totals ([#78](https://github.com/lykinsbd/naas/issues/78))
- Add DELETE endpoint for job cancellation ([#178](https://github.com/lykinsbd/naas/issues/178))
- Healthcheck endpoint now reports worker count, active jobs, and a `no_workers` status when no RQ workers are available ([#179](https://github.com/lykinsbd/naas/issues/179))
- Add structured audit events for job lifecycle and device failures ([#180](https://github.com/lykinsbd/naas/issues/180))

## 🐛 Bug Fixes

- Fix connection pool key to include password hash, preventing credential sharing between users with the same username ([#196](https://github.com/lykinsbd/naas/issues/196))

## 📚 Documentation

- Add Kubernetes deployment manifests and documentation for k3d/k8s deployment ([#28](https://github.com/lykinsbd/naas/issues/28))
- Document connection pool configuration variables in kubernetes.md and k8s/configmap.yaml ([#191](https://github.com/lykinsbd/naas/issues/191))
- Document TLS certificate encoding requirements for NAAS_CERT/NAAS_KEY/NAAS_CA_BUNDLE in kubernetes.md ([#192](https://github.com/lykinsbd/naas/issues/192))
- Add 400 status code to CancelJob.delete() docstring ([#193](https://github.com/lykinsbd/naas/issues/193))
- Document required fields per event type in emit_audit_event docstring ([#194](https://github.com/lykinsbd/naas/issues/194))
- Add exposed metrics list to Monitoring section in kubernetes.md ([#195](https://github.com/lykinsbd/naas/issues/195))

## 🧪 Testing & CI/CD

- Add end-to-end job test to k8s CI: deploys Cisshgo into k3d cluster and validates full API → Redis → worker → SSH device job flow ([#189](https://github.com/lykinsbd/naas/issues/189))
- Justify pragma: no cover on cancel_job.py auth guard with inline explanation ([#205](https://github.com/lykinsbd/naas/issues/205))
- Fix contract test to accept no_workers healthcheck status

## 🔧 Internal Changes

- Release workflow now pins k8s manifest image tags to the release version ([#197](https://github.com/lykinsbd/naas/issues/197))
- Cache Worker.all() result with 10s TTL to avoid repeated Redis scans on every request ([#199](https://github.com/lykinsbd/naas/issues/199))
- Add file-based heartbeat to worker process and liveness probe to k8s worker deployment ([#200](https://github.com/lykinsbd/naas/issues/200))

# NAAS 1.1.0 (2026-02-26)

## ✨ Features

- Device IP lockout: after 10 connection failures within 10 minutes, all access to that device is blocked for 10 minutes, preventing credential-spray abuse across multiple users. Also refactors the user lockout to use the same Redis sorted-set sliding-window implementation. ([#2](https://github.com/lykinsbd/naas/issues/2))
- All log output is now structured JSON, making logs parseable by ELK, Splunk, CloudWatch, and other log aggregation tools. Each log line includes `timestamp`, `level`, `logger`, and `message` fields. ([#79](https://github.com/lykinsbd/naas/issues/79))
- Correlation ID (request_id/job_id) now flows from API request through to worker log messages, enabling end-to-end log tracing across API and worker. ([#80](https://github.com/lykinsbd/naas/issues/80))
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
- Fix job.get_id() → job.id (rq removed get_id() in a recent release); was causing 500 errors on all job submissions.

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

- Automate cleanup of released changelog fragments from develop ([#107](https://github.com/lykinsbd/naas/issues/107))
- Add invoke export-spec task and CI check to keep docs/swagger/openapi.json in sync with code; remove stale docs/swagger/naas.yaml ([#128](https://github.com/lykinsbd/naas/issues/128))
- Audit and fix all lint/type-checking exemptions: add types-paramiko stubs, fix hset int->str args, remove dead auth guard in get_results, add inline justification for all remaining ignores. ([#154](https://github.com/lykinsbd/naas/issues/154))
- Extract circuit breaker infrastructure into naas/library/circuit_breaker.py; deduplicate circuit breaker wrapper in netmiko_lib.py; lazy-init Redis client to prevent import-time failure when Redis is unavailable ([#161](https://github.com/lykinsbd/naas/issues/161))
- Remove dead validation methods from Validate class (has_port, is_ip_addr, save_config, commit, is_command_set, has_platform, has_delay_factor) — Pydantic models in models.py handle all request validation now ([#162](https://github.com/lykinsbd/naas/issues/162))
- Move mypy into the enforced lint job so type errors block CI. Previously mypy ran with continue-on-error=true in a separate job and failures were silently ignored.

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

# NAAS 1.0.0 (2026-02-23)

## ⚠️ Deprecations

- Rename `device_type` parameter to `platform` to match Netmiko naming convention (backward compatibility maintained in v1.x) ([#25](https://github.com/lykinsbd/naas/issues/25))

## ✨ Features

- Migrate from Docker Swarm to Docker Compose for simpler deployment and better developer experience ([#29](https://github.com/lykinsbd/naas/issues/29))

## 📚 Documentation

- Add comprehensive user documentation including quick start guide, API usage examples, troubleshooting guide, and security best practices ([#3](https://github.com/lykinsbd/naas/issues/3))

## 🧪 Testing & CI/CD

- Implement comprehensive CI/CD pipeline with GitHub Actions including automated testing, linting, and Docker builds ([#34](https://github.com/lykinsbd/naas/issues/34))
- Achieve 100% test coverage with comprehensive unit, integration, and contract tests ([#47](https://github.com/lykinsbd/naas/issues/47))

## 🔧 Internal Changes

- [#27](https://github.com/lykinsbd/naas/issues/27), [#60](https://github.com/lykinsbd/naas/issues/60), [#65](https://github.com/lykinsbd/naas/issues/65), [#68](https://github.com/lykinsbd/naas/issues/68), [#70](https://github.com/lykinsbd/naas/issues/70), [#71](https://github.com/lykinsbd/naas/issues/71)
