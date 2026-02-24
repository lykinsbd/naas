# NAAS Development Agent

You are assisting with development of NAAS (Netmiko As A Service), a REST API wrapper for Netmiko.

## Critical Workflow Rules

### 1. Issue-First Development

- **ALWAYS** create or link to a GitHub issue before starting work
- Issue should describe the problem/feature clearly
- Use appropriate labels (enhancement, bug, documentation, security, testing)
- Assign to milestone (v1.1, v1.2, etc.) if applicable
- For related work, use parent/child issue relationships

### 2. Changelog Fragments (MANDATORY)

- **EVERY PR MUST HAVE A CHANGELOG FRAGMENT**
- Create fragment before committing: `uv run towncrier create <issue#>.<type>.md --content "Description"`
- Fragment types:
  - `feature` - New features
  - `bugfix` - Bug fixes
  - `security` - Security improvements
  - `breaking` - Breaking changes
  - `deprecation` - Deprecations
  - `doc` - Documentation
  - `testing` - Testing/CI improvements
  - `internal` - Internal changes (not shown to users)
- For work without issue number, use `+` prefix: `+description.type.md`
- **CHECK BEFORE EVERY COMMIT:** "Did I create the fragment?"

### 3. Branching Strategy (Long-lived Release Branches)

**Branch Types:**

- `main` - Production releases only (v1.0.0, v1.1.0, v1.1.1)
- `develop` - Integration branch (v1.2.0a1, v1.2.0a2)
- `release/X.Y` - Maintenance branches (KEPT FOREVER)
  - `release/1.0` - All v1.0.x patches
  - `release/1.1` - All v1.1.x patches

**Feature Branches (from develop):**

- `feature/` - New features
- `fix/` - Bug fixes in development
- `docs/` - Documentation changes
- `test/` - Test additions
- `chore/` - Maintenance tasks
- `refactor/` - Code refactoring

**Hotfix Branches (from release/X.Y):**

- `hotfix/` - Critical fixes for released versions
- Branch from appropriate `release/X.Y`, NOT from main
- Merge to `release/X.Y` → `main` → `develop`

**Decision Tree:**

```text
Need to make a change?
  │
  ├─ New feature/enhancement?
  │    └─→ Branch from develop, target develop
  │
  ├─ Bug in unreleased code (develop)?
  │    └─→ Branch from develop, target develop
  │
  ├─ Bug in current release (v1.1.x)?
  │    └─→ Branch from release/1.1, target release/1.1
  │
  ├─ Bug in old release (v1.0.x)?
  │    └─→ Branch from release/1.0, target release/1.0
  │
  └─ Documentation-only change?
       └─→ Can branch from develop OR main (if urgent)
```

**ALWAYS ASK:** "What's the correct base branch for this work?"

### 4. Conventional Commits (REQUIRED)

Format: `<type>(<scope>): <description>`

**Types:**

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting)
- `refactor` - Code refactoring
- `test` - Adding/updating tests
- `chore` - Maintenance tasks
- `perf` - Performance improvements
- `ci` - CI/CD changes

**Breaking changes:** Add `!` after type or `BREAKING CHANGE:` in footer

**Examples:**

```bash
feat(api): add pagination to job history endpoint
fix(worker): resolve connection leak in netmiko wrapper
docs: update branching strategy in CONTRIBUTING.md
chore(deps): upgrade netmiko to 4.6.0
```

### 5. Pull Request Workflow

**Before creating PR:**

1. ✅ Issue created/linked
2. ✅ Changelog fragment added
3. ✅ Tests added/updated (if applicable)
4. ✅ Documentation updated (if applicable)
5. ✅ All commits follow conventional format
6. ✅ Targeting correct base branch

**PR Description:**

- Link to issue: "Closes #123" or "Relates to #123"
- Summarize changes
- Note any breaking changes
- List testing performed

**Merge Strategy:**

- Squash merge for feature branches (multiple commits)
- Rebase merge for clean history (single/few commits)
- Never merge commits (no merge bubbles)

### 6. Testing Requirements

- Unit tests for new functions/classes
- Integration tests for API endpoints
- Contract tests for API behavior
- Maintain or improve code coverage
- Use `pytest` for all tests
- Use `fakeredis` for Redis-dependent tests

### 7. Code Quality

**Before committing:**

- Run `invoke check` (linting, formatting, type checking)
- Fix any ruff or mypy errors
- Ensure pre-commit hooks pass

**Standards:**

- Use type hints throughout
- Write docstrings for public functions
- Keep functions small and focused
- Follow existing code patterns

## Project-Specific Context

### Current State

- **Version:** v1.0.0 released, develop at v1.1.0a1
- **Active branches:** main, develop, release/1.0, release/1.1
- **Milestone:** v1.1 (30+ issues planned)

### Key Technologies

- Python 3.11+
- Flask (API framework)
- RQ (job queue)
- Redis (queue backend)
- Netmiko (device connectivity)
- uv (dependency management)
- Docker Compose (deployment)

### Important Files

- `pyproject.toml` - Project config, dependencies, version
- `CONTRIBUTING.md` - Development guidelines
- `CHANGELOG.md` - Generated from fragments
- `changes/` - Changelog fragments directory
- `changes/template.md.j2` - Changelog template

### Common Tasks

```bash
# Create fragment
uv run towncrier create 123.feature.md --content "Add new feature"

# Run tests
invoke test

# Code quality
invoke check

# Create issue
gh issue create --title "Title" --body "Description" --label enhancement

# Create PR
gh pr create --base develop --title "Title" --body "Description"
```

## Proactive Checks

**Before every commit:**

- "Did I create a changelog fragment?"
- "Are my commits conventional?"

**Before every PR:**

- "Is there an issue linked?"
- "Am I targeting the correct base branch?"
- "Did I update documentation if needed?"

**When creating issues:**

- "Should this be a child of a parent issue?"
- "What's the appropriate milestone?"
- "Are the labels correct?"

**When branching:**

- "Am I branching from the correct base?"
- "Is my branch name following conventions?"

## Reminders

- Release branches are NEVER deleted (long-lived)
- Hotfixes go to release/X.Y first, then main, then develop
- Documentation-only changes can go directly to main if urgent
- Internal type fragments don't show in user-facing changelog
- Always use `--force-with-lease` instead of `--force` for safety
- Sign commits with GPG when possible (`-S` flag)

## When in Doubt

1. Check CONTRIBUTING.md for documented workflow
2. Look at recent PRs for examples
3. Ask the user before making assumptions
4. Default to conservative approach (create issue, add fragment, target develop)
