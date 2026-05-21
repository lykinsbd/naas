# Architectural Decision Records

This directory contains Architectural Decision Records (ADRs) for NAAS, using the [MADR format](https://adr.github.io/madr/).

## What is an ADR?

An ADR documents a significant architectural or technical decision: what was decided, why, and what the consequences are. ADRs are immutable once accepted — if a decision changes, a new ADR supersedes the old one.

## When to Write an ADR

Write an ADR when:

- Choosing between two or more non-trivial technical approaches
- Making a decision that would be hard to reverse
- Adopting a new tool, pattern, or dependency that affects the whole project
- Deciding on a convention that all contributors must follow

Do **not** write an ADR for:

- Implementation details (use code comments or PR descriptions)
- Bug fixes
- Routine dependency updates

## How to Add an ADR

1. Copy `template.md` to `NNNN-short-title.md` (next sequential number)
2. Fill in all sections
3. Set status to `Proposed`
4. Open a PR — discussion happens in the PR review
5. On merge, update status to `Accepted`

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-python-client-library-integration.md) | Python client library integration strategy | Accepted |
| [0002](0002-secrets-backend-abstraction.md) | Secrets backend abstraction | Accepted |
| [0003](0003-api-key-authentication.md) | API key authentication | Accepted |
| [0004](0004-role-based-access-control.md) | Role-based access control | Accepted |
| [0005](0005-structured-audit-event-logging.md) | Structured audit event logging | Accepted |
| [0006](0006-credential-encryption-at-rest.md) | Credential encryption at rest | Accepted |
| [0007](0007-api-versioning-strategy.md) | API versioning strategy | Accepted |
| [0008](0008-opentelemetry-instrumentation-strategy.md) | OpenTelemetry instrumentation strategy | Accepted |
| [0009](0009-command-authorization-deferred-to-aaa.md) | Command authorization deferred to AAA | Accepted |
| [0010](0010-mcp-server-thin-client-over-rest-api.md) | MCP server as thin client over REST API | Accepted |
| [0011](0011-release-process.md) | Release branch as the source of truth during a release | Accepted |
