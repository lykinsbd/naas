# Python Client Library Integration Strategy

* Status: Accepted (amended 2026-04-09)
* Date: 2026-03-18

## Context and Problem Statement

NAAS needs a Python client library (`naas-client`) to simplify integration for users. The question is how to structure and integrate it with the NAAS repository for development and testing — and how to version it relative to the server.

## Decision Drivers

* Minimize CI complexity and contributor friction
* Enable integration tests to validate the client against unreleased NAAS changes
* Maintain clean separation between server and client packages
* Follow standard Python packaging practices
* Allow independent release cadence for the client

## Considered Options

* Git submodule — embed `naas-client` repo inside NAAS repo
* Install at test time — `pip install naas-client` (pinned version) in CI
* **uv workspace member** — co-locate as `packages/naas-client/` in the NAAS monorepo

## Decision Outcome

Chosen option: **uv workspace member**, because it combines the best properties of both alternatives — zero-friction development like "install at test time" with the ability to test unreleased client against unreleased server like "git submodule", without the downsides of either.

The client lives at `packages/naas-client/` alongside `packages/naas/` in the uv workspace. It is developed, tested, and released as an independent PyPI package with its own version.

### Amendment (2026-04-09)

The original decision (2026-03-18) chose "install at test time". After restructuring the repo to a uv workspace layout (#367), the workspace member approach became the natural choice — it eliminates the PyPI-publish-before-testing problem while keeping CI simple.

### Versioning Strategy

`naas-client` uses **independent SemVer**, starting at 1.0.0. The client version tracks the client's Python API surface, not the server version.

* The client targets NAAS `/v2/` endpoints exclusively
* Compatibility is documented: "naas-client 1.x requires NAAS server ≥ 2.0"
* A future NAAS v3 API would require a naas-client 2.0.0 major bump

This follows industry convention — boto3, stripe-python, kubernetes-python, and PyGithub all version independently from their server APIs.

### Consequences

* Good: Test unreleased client against unreleased server — just `uv sync` in the workspace
* Good: No submodule management or PyPI publish required during development
* Good: Independent release cadence — client bugfixes ship without a server release
* Good: Shared lockfile ensures consistent dependency resolution
* Good: Standard `uv run --package naas-client pytest` workflow
* Bad: Client and server share a git history (acceptable for a small team)
* Bad: Must ensure CI runs client tests when server API changes

## Pros and Cons of the Options

### Git submodule

* Good: Atomic commits across both repos
* Good: Can test unreleased client against unreleased server
* Good: No PyPI publish required to run tests
* Bad: `git submodule update --init` required in CI and local dev
* Bad: Detached HEAD confusion for contributors
* Bad: Client breakage blocks NAAS CI even when NAAS itself is unchanged
* Bad: Adds onboarding friction

### Install at test time

* Good: Zero friction — standard dependency declaration
* Good: Clean CI — just `uv sync --extra dev`
* Good: Client and server fail independently
* Good: Follows Python ecosystem conventions
* Bad: Requires PyPI publish before integration testing new client versions
* Bad: Version pin can drift — requires periodic updates when client releases

### uv workspace member

* Good: Zero friction — `uv sync` resolves both packages from source
* Good: Can test unreleased client against unreleased server simultaneously
* Good: No PyPI publish required during development
* Good: Shared lockfile prevents dependency conflicts
* Good: Independent PyPI releases — client is still a standalone package
* Good: Natural fit after repo restructure to `packages/` layout
* Bad: Shared git history (minor — acceptable for related packages)
* Bad: CI must be path-filtered to avoid unnecessary test runs
