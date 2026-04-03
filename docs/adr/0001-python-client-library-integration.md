# Python Client Library Integration Strategy

* Status: Accepted
* Date: 2026-03-18

## Context and Problem Statement

NAAS needs a Python client library (`naas-client`) to simplify integration for users. The library will be developed as a separate package/repository. The question is how to integrate it with the NAAS repository for testing purposes — specifically, whether to use a git submodule or install it as a dependency at test time.

## Decision Drivers

* Minimize CI complexity and contributor friction
* Enable integration tests to validate the client against NAAS
* Maintain clean separation between NAAS and the client library
* Follow standard Python packaging practices

## Considered Options

* Git submodule — embed `naas-client` repo inside NAAS repo
* Install at test time — `pip install naas-client` (pinned version) in CI

## Decision Outcome

Chosen option: **Install at test time**, because it follows standard Python packaging practices, keeps CI simple, and avoids submodule complexity. The separation of concerns is clean: NAAS is the server, `naas-client` is a consumer like any other.

### Consequences

* Good: No submodule management (`git submodule update --init`) required for contributors
* Good: Client failures don't block NAAS CI — pin a known-good version
* Good: Standard pattern — any Python project can depend on `naas-client` the same way
* Bad: Must publish `naas-client` to PyPI (or GitHub Packages) before testing new client features against unreleased NAAS changes
* Bad: Version pin can drift — requires periodic updates when client releases

## Pros and Cons of the Options

### Git submodule

* Good: Atomic commits across both repos
* Good: Can test unreleased client against unreleased NAAS simultaneously
* Good: No PyPI publish required to run tests
* Bad: `git submodule update --init` required in CI and local dev
* Bad: Detached HEAD confusion for contributors
* Bad: Client breakage blocks NAAS CI even when NAAS itself is unchanged
* Bad: Adds onboarding friction

### Install at test time

* Good: Zero friction — standard dependency declaration
* Good: Clean CI — just `uv sync --extra dev`
* Good: Client and NAAS fail independently
* Good: Follows Python ecosystem conventions
* Bad: Requires PyPI publish before integration testing new client versions
* Bad: Version pin maintenance overhead
