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
| --- | --- |
| `main` | Production releases only (`v1.0.0`, `v1.1.0`) |
| `develop` | Integration branch (`v1.2.0a1`) |
| `release/X.Y` | Maintenance branches — kept permanently |

### Feature branch types (from `develop`)

| Prefix | Use |
| --- | --- |
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
| --- | --- |
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

### Running integration tests locally

Integration tests require Docker. The test suite auto-starts and tears down the stack via `conftest.py`.

```bash
# Run integration tests (starts docker-compose.test.yml automatically)
uv run pytest tests/integration -v --no-cov

# Or via invoke
uv run invoke test-all
```

The integration stack includes:

- **NAAS API** at `https://localhost:18443`
- **Redis** at `localhost:16379` (password: `test_password`)
- **RQ Worker**
- **cisshgo** mock SSH device at `localhost:10022` (platform: `cisco_ios`, credentials: `admin`/`admin`)

To start the stack manually for debugging:

```bash
docker compose -f tests/integration/docker-compose.test.yml up -d --build
# ... run tests or debug ...
docker compose -f tests/integration/docker-compose.test.yml down -v
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
| --- | --- | --- |
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

For the design rationale behind this model, see [ADR 0011: Release branch as the source of truth during a release](adr/0011-release-process.md).

### Version format

- `1.3.0a1` — Alpha (develop only, never released)
- `1.3.0b1` — Beta (pre-release on `release/1.3`)
- `1.3.0rc1` — Release candidate (pre-release on `release/1.3`)
- `1.3.0` — Final release
- `1.3.1` — Patch release (hotfix on `release/1.3`)

### Branch flow

```text
develop (1.3.0a1) → release/1.3 (1.3.0b1 → rc1 → 1.3.0) → main → develop (1.4.0a1)
                                                ↘ release/1.3 (1.3.1) ↗
```

`release/X.Y` is the source of truth during a release. CI never commits to branches — every change is a reviewable human commit. The release ceremony is a single command: `inv release-bump VERSION`.

### The release ceremony

`inv release-bump VERSION` (defined in `packages/naas/tasks.py`) does the entire ceremony in one shot:

1. Validates the working tree is clean and the current branch is `release/X.Y`
2. Validates the target version against the current pyproject.toml version (must be PEP 440-shaped, must match the branch's major.minor, must be strictly greater)
3. Updates `packages/naas/pyproject.toml` to the new version
4. Runs `uv lock` to refresh the lockfile
5. **For final releases only:** pins k8s manifest image tags and runs `towncrier build --yes` (appends a section to `CHANGELOG.md`, deletes consumed fragments)
6. Stages everything that changed, commits with a conventional `chore(release): ...` message, creates an annotated tag at the new commit
7. Pushes branch and tag atomically (`git push --atomic`)

Two flags for safe operation:

- `--dry-run` — print every action without executing. Use this first when you're new to the task.
- `--no-push` — perform every local step but stop before push. Useful for inspecting the commit and tag before they go to origin.

### Step-by-step release process (new minor: X.Y.0)

#### 1. Create the release branch

```bash
git checkout develop
git pull
git checkout -b release/1.3
git push -u origin release/1.3
```

**Base:** Always branch from `develop`.
**Naming:** `release/X.Y` (no patch version).

#### 2. Bump to beta

```bash
# (still on release/1.3)
uv run invoke release-bump 1.3.0b1
```

This bumps `pyproject.toml`, runs `uv lock`, commits, tags `v1.3.0b1`, and atomically pushes commit + tag.

**What happens:** the tag push triggers `release.yml`, which generates the GitHub prerelease. CI does not commit anything back to your branch.

#### 3. Test the beta

- Deploy beta to test environment.
- Run integration tests.
- Fix bugs via PRs to `release/1.3` (NOT `develop`). Each fix should include a changelog fragment.

#### 4. Bump to RC (optional)

If beta needs fixes before final release:

```bash
uv run invoke release-bump 1.3.0rc1
```

Repeat testing. Add more RCs as needed (`rc2`, `rc3`, etc.) — each is one `inv release-bump` invocation.

#### 5. Cut the final release

When the latest RC has been validated:

```bash
# (still on release/1.3)
uv run invoke release-bump 1.3.0
```

For the final release, `inv release-bump` additionally runs `towncrier build --yes`, which appends the new version's section to `CHANGELOG.md` and deletes the consumed fragments. Inspect the diff (the commit shows the version bump, lock refresh, manifest pin, CHANGELOG.md addition, and fragment deletions) before pushing — or use `--no-push` to stop before push.

The tag push triggers `release.yml` to publish the GitHub Release using the section that was just added to `CHANGELOG.md`.

#### 6. Merge release/X.Y → main

```bash
gh pr create --base main --head release/1.3 --title "Release v1.3.0"
```

**Merge with a merge commit, NOT rebase or squash.** This preserves the tagged SHA from `release/1.3` as a real ancestor of `main`, so the tag SHA shows up in `main`'s history. The merge commit itself becomes the "we shipped v1.3.0" event in `main`.

#### 7. Sync back to develop (automated)

When the release/1.3 → main PR merged in step 6, `sync-release.yml` automatically opened:

- A PR `main → develop` (carries the v1.3.0 release commits into develop).
- A PR `chore: bump develop to v1.4.0a1` (only for X.Y.0 releases, not patches).

Review and merge both PRs in any order. **Done.**

### Hotfix process (patch releases)

For bugs in production (e.g., v1.3.0 → v1.3.1):

```bash
# Branch from release/1.3, NOT from main
git checkout release/1.3
git pull
git checkout -b hotfix/issue-description

# Make fixes, add a changelog fragment, commit
git add .
git commit -m "fix: description"
uv run towncrier create <issue#>.bugfix.md --content "Fix description"
git add packages/naas/changes/
git commit -m "docs(changelog): fragment for the fix"

# PR to release/1.3
gh pr create --base release/1.3 --head hotfix/issue-description
```

After the PR merges into `release/1.3`:

```bash
git checkout release/1.3
git pull
uv run invoke release-bump 1.3.1
```

This appends a v1.3.1 section to `CHANGELOG.md`, tags `v1.3.1`, and pushes. Then PR `release/1.3 → main` (merge-commit). When that PR merges, `sync-release.yml` opens a `main → develop` PR; merge that. The develop bump job is skipped for patch releases.

### Common mistakes to avoid

| ❌ Don't | ✅ Do |
| --- | --- |
| Edit `pyproject.toml` by hand for a release | Use `inv release-bump VERSION` |
| Bump version on `develop` before release | Only bump on `release/X.Y` |
| Create release branch from `main` | Always branch from `develop` |
| Use rebase or squash on the release/X.Y → main PR | Use merge commit (preserves tag SHAs in main) |
| Run `towncrier build` manually | `inv release-bump X.Y.Z` does it for finals; prereleases skip it |
| Edit `CHANGELOG.md` by hand for a release | `inv release-bump` appends sections via towncrier |
| Branch hotfixes from `main` | Branch from `release/X.Y` |
| Delete `release/X.Y` branches | Keep them forever (protected by repo ruleset) |

### Version bump locations

- **Only edit:** `packages/naas/pyproject.toml` — but use `inv release-bump`, not a hand edit.
- **Auto-updated by `inv release-bump`:** `uv.lock`, `CHANGELOG.md` (final releases only), `k8s/api/deployment.yaml`, `k8s/worker/deployment.yaml`.
- **Never edit by hand for releases:** `CHANGELOG.md` content above the towncrier marker. (It IS fine to edit older CHANGELOG.md content for typo fixes or back-corrections — those are normal docs PRs to develop.)

### What CI does for releases

CI's only release job is to create the GitHub Release artifact after a tag is pushed:

- `release.yml` (triggered by `push: tags: 'v*'`) validates the tag, extracts the changelog excerpt for finals (or renders unconsumed fragments via `towncrier build --draft` for prereleases), generates the Postman + OpenAPI release artifacts, and creates the GitHub Release.
- `sync-release.yml` (triggered when a `release/X.Y → main` PR merges, finals only) opens the `main → develop` sync PR and the develop-bump PR.

CI does NOT bump versions, write to `CHANGELOG.md`, push tags, or commit to branches. All of that is the human's responsibility, done in one shot via `inv release-bump`.

## Dependency Management

NAAS uses `uv` with `uv.lock` as the source of truth. The Dockerfile uses `uv.lock` directly — there is no `requirements.lock` to maintain.

```bash
uv add package-name           # Add runtime dependency
uv add --dev package-name     # Add dev dependency
# Commit both pyproject.toml and uv.lock
```

## Architectural Decision Records (ADRs)

Significant architectural decisions are documented as ADRs in `docs/adr/` using [MADR format](https://adr.github.io/madr/).

**When to write an ADR:** choosing between non-trivial technical approaches, adopting a new tool or pattern, or making a hard-to-reverse decision.

**How to add one:**

```bash
# Copy the template and fill it in
cp docs/adr/template.md docs/adr/NNNN-short-title.md
# Open a PR — discussion happens in review
# Update docs/adr/README.md index
```

See [docs/adr/README.md](adr/README.md) for the full process.
