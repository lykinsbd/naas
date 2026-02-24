# Contributing to NAAS

Thank you for your interest in contributing to NAAS (Netmiko As A Service)!

## Development setup

1. Install [uv](https://github.com/astral-sh/uv):

```bash
1. Install [uv](https://github.com/astral-sh/uv):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
brew install uv
```

2. Clone and setup:

```bash
git clone https://github.com/lykinsbd/naas.git
cd naas
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
```

3. Install pre-commit hooks:

```bash
pre-commit install
```

4. Run tests:

```bash
pytest
```

## Development Commands

We use [invoke](https://www.pyinvoke.org/) for common development tasks:

```bash
# Install dependencies
invoke install

# Code quality
invoke lint          # Run ruff linter
invoke format        # Format code with ruff
invoke typecheck     # Run mypy type checker
invoke check         # Run all code checks

# Testing
invoke test          # Run unit tests with coverage
invoke test-all      # Run all tests (unit + integration)

# Documentation
invoke docs-lint     # Check markdown style
invoke docs-prose    # Check writing quality (Vale)
invoke docs-links    # Check for broken links
invoke docs-check    # Run all docs checks

# Utilities
invoke clean         # Remove generated files
```

List all available tasks:

```bash
invoke --list
```

### Installing Documentation Tools

To run documentation checks locally, install the tools:

```bash
# markdownlint
npm install -g markdownlint-cli2

# Vale
brew install vale  # macOS
# OR
# Download from https://vale.sh/docs/vale-cli/installation/

# markdown-link-check
npm install -g markdown-link-check
```

## Branching Strategy

NAAS uses a **Git Flow-inspired** branching model with long-lived release branches for maintenance.

### Long-lived Branches

- **`main`** - Production releases only (v1.0.0, v1.1.0, v1.1.1, etc.)
- **`develop`** - Integration branch for ongoing development (v1.2.0a1, v1.2.0a2, etc.)
- **`release/X.Y`** - Maintenance branches for each major.minor version (kept permanently)
  - `release/1.0` - All v1.0.x patches
  - `release/1.1` - All v1.1.x patches
  - `release/1.2` - All v1.2.x patches

### Short-lived Feature Branches

Branch off `develop` using these prefixes (except `docs/` which branches from `main`):

- `feature/` - New features (from develop)
- `fix/` - Bug fixes (from develop)
- `docs/` - Documentation changes (from **main** - required for Read the Docs)
- `test/` - Test additions or modifications (from develop)
- `chore/` - Maintenance (dependencies, config, tooling) (from develop)
- `refactor/` - Code refactoring without behavior changes (from develop)

### Short-lived Hotfix Branches

Branch off the appropriate `release/X.Y` branch:

- `hotfix/` - Critical fixes for released versions

**IMPORTANT:** All merges to `main` must go through pull requests, including:

- Release branches → main
- Hotfix branches → main
- Never merge directly to main without PR review

### Branch Lifecycle

```text
develop (v1.1.0a1) ─────────────────────────────────────┐
  │                                                      │
  ├─ feature/new-feature ─→ develop (via PR)            │
  │                                                      │
  └─→ release/1.1 (created for v1.1 release) ───────────┤
        │                                                │
        ├─ v1.1.0b1 (beta testing)                      │
        ├─ v1.1.0rc1 (release candidate)                │
        └─→ main (v1.1.0 released via PR) ──────────────┤
              │                                          │
              └─→ develop (sync back) ───────────────────┘

release/1.1 (KEPT for v1.1.x maintenance)
  │
  ├─ hotfix/fix-bug ─→ release/1.1 (v1.1.1 via PR)
  │                      │
  │                      ├─→ main (v1.1.1 released via PR)
  │                      └─→ develop (merge back via PR)
  │
  └─ hotfix/another-fix ─→ release/1.1 (v1.1.2 via PR)
                           │
                           ├─→ main (v1.1.2 released via PR)
                           └─→ develop (merge back via PR)
```

### Workflow Examples

#### New Feature Development

```bash
# Start feature from develop
git checkout develop
git pull
git checkout -b feature/add-api-versioning

# Develop and commit
git commit -m "feat: add API versioning support"

# Create PR targeting develop
gh pr create --base develop --title "Add API versioning"
```

#### Documentation Changes

```bash
# Documentation changes target main (for Read the Docs)
git checkout main
git pull
git checkout -b docs/update-api-guide

# Update docs and commit
git commit -m "docs: update API usage guide"

# Create PR targeting main
gh pr create --base main --title "Update API usage guide"
```

#### Bug Fix in Development

```bash
# Fix bug on develop
git checkout develop
git checkout -b fix/redis-connection-leak

# Fix and commit
git commit -m "fix: resolve Redis connection leak"

# Create PR targeting develop
gh pr create --base develop --title "Fix Redis connection leak"
```

#### Hotfix for Current Release (v1.1.x)

```bash
# Branch from release/1.1
git checkout release/1.1
git pull
git checkout -b hotfix/security-patch

# Fix the issue
git commit -m "fix: patch security vulnerability CVE-2026-1234"

# Create PR targeting release/1.1
gh pr create --base release/1.1 --title "Security patch for v1.1.x"

# After merge to release/1.1:
# 1. Bump version to v1.1.1 in pyproject.toml
# 2. Merge release/1.1 → main (triggers v1.1.1 release)
# 3. Merge release/1.1 → develop (resolve conflicts if any)
```

#### Hotfix for Old Release (v1.0.x while v1.1 is current)

```bash
# Branch from release/1.0
git checkout release/1.0
git pull
git checkout -b hotfix/critical-fix

# Fix the issue
git commit -m "fix: critical bug in v1.0.x"

# Create PR targeting release/1.0
gh pr create --base release/1.0 --title "Critical fix for v1.0.x"

# After merge to release/1.0:
# 1. Bump version to v1.0.3 in pyproject.toml
# 2. Merge release/1.0 → main (triggers v1.0.3 release)
# 3. Cherry-pick to release/1.1 if applicable
# 4. Merge to develop if applicable
```

### Release Branch Management

#### Creating a Release Branch

```bash
# When ready to start v1.2 release cycle
git checkout develop
git pull
git checkout -b release/1.2

# Bump to beta version
# Edit pyproject.toml: version = "1.2.0b1"
git commit -m "chore: bump version to 1.2.0b1"
git push -u origin release/1.2

# Create PR: release/1.2 → main
```

#### Release Branch Lifecycle

1. **Created** - When starting release cycle (from develop)
2. **Beta/RC testing** - Pre-releases on release branch
3. **Final release** - Merge to main (v1.2.0)
4. **Kept forever** - For v1.2.x maintenance

#### When to Delete Release Branches

**Never.** Release branches are kept permanently for:

- Patch releases (v1.1.1, v1.1.2, etc.)
- Security updates to older versions
- Historical reference
- Supporting multiple versions simultaneously

### Hotfix Decision Tree

```text
Need to fix a bug?
  │
  ├─ Bug in unreleased code (develop)?
  │    └─→ Create fix/ branch from develop
  │
  ├─ Bug in current release (v1.1.x)?
  │    └─→ Create hotfix/ branch from release/1.1
  │         └─→ Merge to release/1.1 → main → develop
  │
  └─ Bug in old release (v1.0.x)?
       └─→ Create hotfix/ branch from release/1.0
            └─→ Merge to release/1.0 → main
            └─→ Cherry-pick to newer releases if needed
```text
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting, no logic change)
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks
- `perf` - Performance improvements
- `ci` - CI/CD changes

### Breaking Changes

Add `!` after type or `BREAKING CHANGE:` in footer:

```text
feat!: remove support for Python 3.10

BREAKING CHANGE: Minimum Python version is now 3.11
```

### Commit Message Examples

```text
feat(api): add pagination to device list endpoint
fix(worker): resolve RQ 2.x compatibility issue
docs: update Docker Compose deployment instructions
chore(deps): upgrade netmiko to 4.6.0
```

## Pull Request Process

1. Create feature branch from `develop`
2. Make changes with conventional commits
3. Update documentation if needed
4. Add tests for new functionality
5. Ensure all tests pass
6. Create PR targeting `develop`
7. Reference related issues (e.g., "Closes #30")
8. PRs will be merged using **squash** or **rebase** (no merge commits)

### Merge Strategy

- **Squash merge**: Preferred for feature branches with multiple commits
- **Rebase merge**: Preferred for single, clean commits
- **Merge commits**: Avoided to keep history linear and clean

## Code Style

We use automated code quality tools to maintain consistent standards:

### Ruff (Linting & Formatting)

- Fast Python linter and formatter
- Replaces flake8, isort, and more
- Auto-fixes most issues

### Mypy (Type Checking)

- Static type checker
- Gradual typing support
- Catches type errors early

### Pre-commit Hooks

Code quality checks run automatically on commit:

- Ruff linting with auto-fix
- Ruff formatting
- Mypy type checking

To run manually:

```bash
invoke format  # Format and fix issues
invoke check   # Run all checks
```

### Guidelines

- Follow PEP 8 (enforced by ruff)
- Use type hints where appropriate
- Add docstrings for public functions/classes
- Keep functions focused and concise
- Line length: 120 characters

## Testing

- Write tests for new features
- Maintain or improve code coverage
- Use `pytest` for test execution
- Use `fakeredis` for Redis-dependent tests

## Changelog Fragments

Every pull request must include a changelog fragment describing the change.

### Creating a Fragment

When you create a PR, add a news fragment file:

```bash
# Using invoke task
invoke changelog-create --pr=123 --type=feature --content="Add connection pooling"

# Or manually create the file
echo "Add connection pooling for improved performance" > changes/123.feature.md
```

### Fragment Without Issue Number

For minor fixes or internal changes without a GitHub issue, use the `+` prefix:

```bash
# Create fragment without issue number
echo "Fix typo in error message" > changes/+typo-fix.bugfix.md
```

These fragments won't include an issue link in the changelog.

### Fragment Types

Choose the appropriate type for your change:

- `feature` - New features
- `bugfix` - Bug fixes
- `security` - Security improvements
- `breaking` - Breaking changes (API changes, removed features)
- `deprecation` - Deprecations (features marked for removal)
- `doc` - Documentation improvements
- `testing` - Testing and CI/CD improvements
- `internal` - Internal changes (refactoring, dependencies)

**Note:** `internal` type changes are not shown in user-facing changelogs.

### Fragment Content Guidelines

Write for end users, not developers:

**Good:**

```markdown
Add connection pooling to reduce latency for repeated requests
```

**Bad:**

```markdown
Refactor netmiko_lib.py to use ConnectionPool class
```

**Tips:**

- Use present tense: "Add", "Fix", "Improve"
- Be specific about the benefit or impact
- Keep it concise (one line preferred)
- Use technical terms when appropriate for the audience

### Preview Changelog

See how your fragment will appear:

```bash
invoke changelog-draft
```

### CI Validation

CI will fail if your PR is missing a changelog fragment. The error message will show you how to create one.

## Release Process

NAAS uses automated releases triggered by version changes in `pyproject.toml`.

### Version Format

- **Alpha**: `1.0.0a1` (no release)
- **Beta**: `1.0.0b1` (pre-release on release branch)
- **RC**: `1.0.0rc1` (pre-release on release branch)
- **Release**: `1.0.0` (full release on main)

### Release Workflow

#### Complete Release Flow

```text
develop (1.0.0a1) → release/1.0 (1.0.0b1 → 1.0.0rc1 → 1.0.0) → main (1.0.0)
```

#### Step 1: First Beta Release

1. **Sync release branch** from develop:

   ```bash
   # Create PR: develop → release/1.0
   # Merge to bring release branch up to date
   ```

2. **Bump to beta** on release branch:

   ```bash
   git checkout release/1.0
   git pull
   git checkout -b bump/1.0.0b1
   # Edit pyproject.toml: version = "1.0.0b1"
   # Create PR: bump/1.0.0b1 → release/1.0
   ```

3. **After merge**, CI automatically:
   - Builds changelog (keeps fragments)
   - Creates git tag `v1.0.0b1`
   - Creates GitHub pre-release with beta warning

#### Step 2: Additional Beta/RC Releases

Repeat version bumps on release branch as needed:

```bash
# For beta 2
version = "1.0.0b2"

# For RC 1
version = "1.0.0rc1"

# For RC 2
version = "1.0.0rc2"
```

Each merge to `release/1.0` triggers a new pre-release.

#### Step 3: Final Release

1. **Bump to final version** on release branch:

   ```bash
   git checkout release/1.0
   git pull
   git checkout -b bump/1.0.0
   # Edit pyproject.toml: version = "1.0.0"
   # Create PR: bump/1.0.0 → release/1.0
   # Merge
   ```

2. **Merge release to main**:

   ```bash
   # Create PR: release/1.0 → main
   # Merge (brings version 1.0.0 to main)
   ```

3. **After merge to main**, CI automatically:
   - Builds changelog (deletes fragments)
   - Creates git tag `v1.0.0`
   - Creates GitHub release (no warning)

#### Step 4: Sync Back to Develop

After final release, sync main back to develop:

```bash
# Create PR: main → develop
# Bump develop to next alpha: version = "1.1.0a1"
```

### Pre-release Behavior

**Alpha** (`1.0.0a1`) on develop:

- No release triggered
- For development only

**Beta** (`1.0.0b1`) on release/X.Y:

- Creates GitHub pre-release
- Builds changelog (keeps fragments)
- Warning: "Beta software - APIs may change"

**RC** (`1.0.0rc1`) on release/X.Y:

- Creates GitHub pre-release
- Builds changelog (keeps fragments)
- Warning: "Release candidate - only critical fixes"

**Release** (`1.0.0`) on main:

- Creates full GitHub release
- Builds changelog (deletes fragments)
- No warning

### Branch Strategy

- **develop** → Alpha versions (`1.1.0a1`, `1.1.0a2`)
- **release/X.Y** → Beta/RC versions (`1.1.0b1`, `1.1.0rc1`)
- **main** → Release versions (`1.1.0`)

### Release Triggers

- **Alpha** (`1.0.0a1`) → No release (develop only)
- **Beta** (`1.0.0b1`) → Pre-release on release branch
- **RC** (`1.0.0rc1`) → Pre-release on release branch
- **Release** (`1.0.0`) → Full release on main

## Questions

Open an issue for discussion or reach out to maintainers.
