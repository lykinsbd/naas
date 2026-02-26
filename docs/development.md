# Development Guide

Reference documentation for NAAS contributors and maintainers.

## Development Commands

We use [invoke](https://www.pyinvoke.org/) for common development tasks:

```bash
# Code quality
uv run invoke lint          # Run ruff linter
uv run invoke format        # Format code with ruff
uv run invoke typecheck     # Run mypy type checker
uv run invoke check         # Run all code checks (lint + typecheck)

# Testing
uv run invoke test          # Run unit tests with coverage
uv run invoke test-all      # Run all tests (unit + integration)

# Documentation
uv run invoke docs-lint     # Check markdown style
uv run invoke docs-prose    # Check writing quality (Vale)
uv run invoke docs-links    # Check for broken links
uv run invoke docs-check    # Run all docs checks

# Utilities
uv run invoke export-spec   # Regenerate docs/swagger/openapi.json
uv run invoke clean         # Remove generated files
```

## Branching Strategy

NAAS uses a Git Flow-inspired model with long-lived release branches.

### Long-lived branches

| Branch | Purpose |
|---|---|
| `main` | Production releases only (`v1.0.0`, `v1.1.0`) |
| `develop` | Integration branch (`v1.2.0a1`) |
| `release/X.Y` | Maintenance branches — kept permanently |

### Feature branch types (from `develop`)

| Prefix | Use |
|---|---|
| `feature/` | New features |
| `fix/` | Bug fixes in unreleased code |
| `docs/` | Documentation changes |
| `chore/` | Maintenance tasks |
| `refactor/` | Code refactoring |

### Hotfix branches (from `release/X.Y`)

Branch from the appropriate `release/X.Y`, not from `main`. Merge to `release/X.Y` → `main` → `develop`.

### Decision tree

```text
New feature/enhancement?       → branch from develop, target develop
Bug in unreleased code?        → branch from develop, target develop
Bug in current release (v1.1)? → branch from release/1.1, target release/1.1
Documentation only?            → branch from main, target main (Read the Docs)
```

## Conventional Commits

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>
```

| Type | Use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code refactoring |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |
| `perf` | Performance improvements |

Breaking changes: add `!` after type (`feat!:`) or `BREAKING CHANGE:` in footer.

## Code Style

- **Ruff** — linting and formatting (replaces flake8, isort, black)
- **Mypy** — static type checking
- **Pre-commit** — runs both automatically on commit

Standards:

- Type hints throughout
- Google-style docstrings for public functions
- Line length: 120 characters
- `list[str]` over `List[str]` (Python 3.11+)

## Testing

- 100% unit test coverage required — CI will fail below this threshold
- Use `pytest` for all tests
- Use `fakeredis` for Redis-dependent tests
- Mock external dependencies (network calls, device connections)

```bash
uv run invoke test          # unit tests + coverage report
uv run invoke test-all      # unit + integration tests
```

## Changelog Fragments

Every PR must include a changelog fragment. CI will fail without one.

```bash
# Create a fragment
uv run towncrier create <issue#>.<type>.md --content "Description for end users"

# For work without an issue number
uv run towncrier create +description.<type>.md --content "Description"

# Preview how it will render
uv run invoke changelog-draft
```

### Fragment types

| Type | Shown to users | Use |
|---|---|---|
| `feature` | ✅ | New features |
| `bugfix` | ✅ | Bug fixes |
| `security` | ✅ | Security improvements |
| `breaking` | ✅ | Breaking changes |
| `deprecation` | ✅ | Deprecations |
| `doc` | ✅ | Documentation |
| `testing` | ✅ | Testing/CI improvements |
| `internal` | ❌ | Internal changes (refactoring, deps) |

Write for end users, not developers. Use present tense. Be specific about the benefit.

## Release Process

### Version format

- `1.1.0a1` — Alpha (develop only, no release)
- `1.1.0b1` — Beta (pre-release on `release/1.1`)
- `1.1.0rc1` — Release candidate (pre-release on `release/1.1`)
- `1.1.0` — Final release (on `main`)

### Flow

```text
develop (1.1.0a1) → release/1.1 (1.1.0b1 → rc1 → 1.1.0) → main (1.1.0)
```

1. Create PR from `develop` → `release/1.1` to sync
2. Bump version on `release/1.1`, create PR, merge → CI creates pre-release tag
3. Repeat for RC as needed
4. Bump to final version, merge to `release/1.1`, then PR `release/1.1` → `main`
5. After merge to `main`, CI creates full release tag and deletes changelog fragments
6. Create PR `main` → `develop`, bump develop to next alpha

### After release

Sync `main` back to `develop` and bump to the next alpha version (`1.2.0a1`).

## Dependency Management

NAAS uses `uv` with `uv.lock` as the source of truth. The Dockerfile uses `uv.lock` directly — there is no `requirements.lock` to maintain.

```bash
uv add package-name           # Add runtime dependency
uv add --dev package-name     # Add dev dependency
# Commit both pyproject.toml and uv.lock
```
