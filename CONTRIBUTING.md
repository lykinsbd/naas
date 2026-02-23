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

### Long-lived Branches

- `main` - Stable, production-ready code
- `develop` - Integration branch for ongoing development
- `release/X.Y` - Release preparation branches

### Short-lived Feature Branches

Branch off `develop` using these prefixes:

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Test additions or modifications
- `chore/` - Maintenance (dependencies, config, tooling)
- `refactor/` - Code refactoring without behavior changes

Emergency fixes:

- `hotfix/` - Critical fixes branched from `main`

### Examples

```bash
# Feature branch
git checkout develop
git checkout -b feature/add-api-versioning

# Bug fix
git checkout develop
git checkout -b fix/redis-connection-leak

# Hotfix
git checkout main
git checkout -b hotfix/security-patch
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
