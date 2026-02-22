# Contributing to NAAS

Thank you for your interest in contributing to NAAS (Netmiko As A Service)!

## Development Setup

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

3. Run tests:
```bash
pytest
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
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
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
```
feat!: remove support for Python 3.10

BREAKING CHANGE: Minimum Python version is now 3.11
```

### Examples
```
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

- Follow PEP 8
- Use type hints where appropriate
- Add docstrings for public functions/classes
- Keep functions focused and concise

## Testing

- Write tests for new features
- Maintain or improve code coverage
- Use `pytest` for test execution
- Use `fakeredis` for Redis-dependent tests

## Questions?

Open an issue for discussion or reach out to maintainers.
