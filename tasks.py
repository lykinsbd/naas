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


@task
def docs_lint(c):
    """Run markdownlint on documentation."""
    c.run("markdownlint-cli2 'README.md' 'CONTRIBUTING.md' 'docs/**/*.md'")


@task
def docs_prose(c):
    """Run Vale prose linter on documentation."""
    c.run("vale --glob='!docs/COVERAGE.md' README.md CONTRIBUTING.md docs/*.md")


@task
def docs_links(c):
    """Check for broken links in documentation."""
    c.run("markdown-link-check README.md CONTRIBUTING.md docs/**/*.md --config .markdown-link-check.json")


@task(pre=[docs_lint, docs_prose, docs_links])
def docs_check(c):
    """Run all documentation checks."""
    print("✅ All documentation checks passed!")


@task
def docs_serve(c):
    """Serve documentation locally (requires mkdocs)."""
    print("📚 MkDocs not yet configured. Coming in future release!")
    print("   For now, view markdown files directly or use a markdown viewer.")


@task
def export_spec(c):
    """Export OpenAPI spec from the running app to docs/swagger/openapi.json."""
    import json
    from unittest.mock import patch

    import fakeredis

    # Patch Redis before importing app (app_configure hits Redis at import time)
    with patch("naas.config.Redis", return_value=fakeredis.FakeStrictRedis()):
        with patch("naas.config.Queue"):
            from naas.app import app

            with app.test_client() as client:
                response = client.get("/apidoc/openapi.json")
                assert response.status_code == 200, f"Failed to fetch spec: {response.status_code}"
                spec = response.get_json()

    output_path = "docs/swagger/openapi.json"
    with open(output_path, "w") as f:
        json.dump(spec, f, indent=2)
        f.write("\n")

    print(f"✅ OpenAPI spec written to {output_path}")


@task
def changelog_draft(c):
    """Preview changelog for next release."""
    c.run("towncrier build --draft --version NEXT")


@task
def changelog_create(c, pr, type, content=""):
    """Create a changelog fragment.

    Args:
        pr: Pull request number
        type: Fragment type (feature, bugfix, security, breaking, deprecation, doc, testing, internal)
        content: Description of the change (optional, will prompt if not provided)
    """
    if content:
        c.run(f"towncrier create {pr}.{type}.md --content '{content}'")
    else:
        c.run(f"towncrier create {pr}.{type}.md --edit")
