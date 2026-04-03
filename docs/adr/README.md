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
