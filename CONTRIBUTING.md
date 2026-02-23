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

## Questions

Open an issue for discussion or reach out to maintainers.
