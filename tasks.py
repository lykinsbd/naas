"""Development tasks for NAAS project."""

from invoke import task


@task
def install(c):
    """Install dependencies."""
    c.run("uv pip sync requirements-dev.lock")


@task
def test(c):
    """Run unit tests with coverage."""
    c.run("pytest tests/unit")


@task
def test_integration(c):
    """Run integration tests with Docker Compose."""
    c.run("pytest tests/integration -v")


@task
def test_all(c):
    """Run all tests (unit + integration)."""
    c.run("pytest")


@task
def lint(c):
    """Run ruff linter."""
    c.run("ruff check naas/ tests/")


@task
def format(c):
    """Format code with ruff."""
    c.run("ruff format naas/ tests/")
    c.run("ruff check naas/ tests/ --fix")


@task
def typecheck(c):
    """Run mypy type checker."""
    c.run("mypy naas/")


@task(pre=[lint, typecheck])
def check(c):
    """Run all checks (lint + type check)."""
    print("✅ All checks passed!")


@task
def clean(c):
    """Remove generated files."""
    c.run("rm -rf .pytest_cache htmlcov .coverage .mypy_cache .ruff_cache")
    c.run("find . -type d -name __pycache__ -exec rm -rf {} +", warn=True)
    c.run("find . -type f -name '*.pyc' -delete", warn=True)
