# Changelog

All notable changes to NAAS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

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
