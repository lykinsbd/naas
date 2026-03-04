# Changelog

All notable changes to NAAS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# NAAS 1.3.0rc1 (2026-03-04)

## 💥 Breaking Changes

- Replace delay_factor parameter with read_timeout (float, seconds) in send_command and send_config endpoints ([#216](https://github.com/lykinsbd/naas/issues/216))

## 🔒 Security

- Run API and worker containers as non-root user (UID 1000) with NET_BIND_SERVICE capability for port 443 ([#198](https://github.com/lykinsbd/naas/issues/198))
- Set readOnlyRootFilesystem on API and worker containers; pre-compile Python bytecode in Dockerfile ([#206](https://github.com/lykinsbd/naas/issues/206))

## ✨ Features

- Add connection pooling for persistent SSH device connections, reducing VTY session overhead on network devices ([#57](https://github.com/lykinsbd/naas/issues/57))
- Add Prometheus metrics endpoint at `/metrics` exposing request counts, latency, queue depth, worker count, and job totals ([#78](https://github.com/lykinsbd/naas/issues/78))
- Add DELETE endpoint for job cancellation ([#178](https://github.com/lykinsbd/naas/issues/178))
- Healthcheck endpoint now reports worker count, active jobs, and a `no_workers` status when no RQ workers are available ([#179](https://github.com/lykinsbd/naas/issues/179))
- Add structured audit events for job lifecycle and device failures ([#180](https://github.com/lykinsbd/naas/issues/180))
- Add /v1/send_command_structured endpoint with TextFSM parsing via ntc-templates or custom templates ([#219](https://github.com/lykinsbd/naas/issues/219))
- Add optional expect_string parameter to send_command for custom prompt matching ([#220](https://github.com/lykinsbd/naas/issues/220))
- Add platform autodetect via SSHDetect for discovery workflows and heterogeneous environments ([#222](https://github.com/lykinsbd/naas/issues/222))

## 🐛 Bug Fixes

- Fix connection pool key to include password hash, preventing credential sharing between users with the same username ([#196](https://github.com/lykinsbd/naas/issues/196))
- Detect config errors via `error_pattern` in `send_config_set`, returning error string instead of succeeding silently ([#217](https://github.com/lykinsbd/naas/issues/217))
- Call find_prompt() after connection pool hit to verify clean CLI state before issuing commands ([#218](https://github.com/lykinsbd/naas/issues/218))
- Use `setnx` for `naas_cred_salt` so API restarts do not invalidate existing connection pool keys and in-flight job auth ([#223](https://github.com/lykinsbd/naas/issues/223))
- Pass Redis connection explicitly to `tacacs_auth_lockout` and `device_lockout`, eliminating per-request TCP connection overhead ([#224](https://github.com/lykinsbd/naas/issues/224))
- Set explicit `job_timeout` on enqueue to prevent hung workers holding for RQ's 180s default ([#226](https://github.com/lykinsbd/naas/issues/226))
- Call `redis.ping()` at startup to fail fast if Redis is unavailable ([#227](https://github.com/lykinsbd/naas/issues/227))

## 📚 Documentation

- Add Kubernetes deployment manifests and documentation for K8s deployment ([#28](https://github.com/lykinsbd/naas/issues/28))
- Document connection pool configuration variables in Kubernetes.md and K8s/configmap.yaml ([#191](https://github.com/lykinsbd/naas/issues/191))
- Document TLS certificate encoding requirements for NAAS_CERT/NAAS_KEY/NAAS_CA_BUNDLE in Kubernetes.md ([#192](https://github.com/lykinsbd/naas/issues/192))
- Add 400 status code to CancelJob.delete() docstring ([#193](https://github.com/lykinsbd/naas/issues/193))
- Document required fields per event type in `emit_audit_event` docstring ([#194](https://github.com/lykinsbd/naas/issues/194))
- Add exposed metrics list to Monitoring section in Kubernetes.md ([#195](https://github.com/lykinsbd/naas/issues/195))

## 🧪 Testing & CI/CD

- Add end-to-end job test to K8s CI: deploys Cisshgo into k3d cluster and validates full API → Redis → worker → SSH device job flow ([#189](https://github.com/lykinsbd/naas/issues/189))
- Justify `pragma: no cover` on cancel_job.py auth guard with inline explanation ([#205](https://github.com/lykinsbd/naas/issues/205))
- Fix contract test to accept `no_workers` healthcheck status

## 🔧 Internal Changes

- Release workflow now pins K8s manifest image tags to the release version ([#197](https://github.com/lykinsbd/naas/issues/197))
- Cache Worker.all() result with 10s TTL to avoid repeated Redis scans on every request ([#199](https://github.com/lykinsbd/naas/issues/199))
- Add file-based heartbeat to worker process and K8s worker deployment liveness probe ([#200](https://github.com/lykinsbd/naas/issues/200))
- Explicitly set fast_cli=True on ConnectHandler for consistent throughput across all platforms ([#221](https://github.com/lykinsbd/naas/issues/221))
- Use Job.fetch_many() in ListJobs to batch-fetch job details in a single Redis pipeline call ([#225](https://github.com/lykinsbd/naas/issues/225))
- Pass Job object directly to `job_locker` to avoid redundant Redis fetch after enqueue ([#228](https://github.com/lykinsbd/naas/issues/228))
- Add comment to `worker_cache` documenting per-process global state assumption ([#229](https://github.com/lykinsbd/naas/issues/229))
- Ignore codecov.io badge URLs in link-check to prevent flaky CI failures ([#234](https://github.com/lykinsbd/naas/issues/234))
- Share Docker image between build.yml and k8s-tests via artifact to eliminate duplicate builds ([#240](https://github.com/lykinsbd/naas/issues/240))

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
