"""Development tasks for NAAS project."""

import re
import sys
from pathlib import Path

from invoke import task

# ---------------------------------------------------------------------------
# Repo-relative paths used by release tasks. tasks.py runs from packages/naas/
# but most release-relevant files live at the repo root, so define both.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYPROJECT_PATH = REPO_ROOT / "packages" / "naas" / "pyproject.toml"
CHANGES_DIR = REPO_ROOT / "packages" / "naas" / "changes"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
K8S_API_DEPLOYMENT = REPO_ROOT / "k8s" / "api" / "deployment.yaml"
K8S_WORKER_DEPLOYMENT = REPO_ROOT / "k8s" / "worker" / "deployment.yaml"

# Match release branches: release/1.0, release/1.3, release/2.1 (X.Y only).
# The historical release/finalize-X.Y.Z branches are not covered here on
# purpose — those are leftover automation branches and the new model
# does not use them.
RELEASE_BRANCH_RE = re.compile(r"^release/(\d+)\.(\d+)$")

# Permissive PEP 440 subset: X.Y.Z, X.Y.ZbN, X.Y.ZrcN. Alphas not allowed
# at release time (alphas live only on develop).
RELEASE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:(b|rc)(\d+))?$")


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
    with c.cd(str(REPO_ROOT)):
        c.run("markdownlint-cli2 'README.md' 'CONTRIBUTING.md' 'docs/**/*.md'")


@task
def docs_prose(c):
    """Run Vale prose linter on documentation."""
    with c.cd(str(REPO_ROOT)):
        c.run("vale --glob='!docs/COVERAGE.md' README.md CONTRIBUTING.md docs/*.md")


@task
def docs_links(c):
    """Check for broken links in documentation."""
    with c.cd(str(REPO_ROOT)):
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

    output_path = "../../docs/swagger/openapi.json"
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


# ---------------------------------------------------------------------------
# Release helpers (used only by the `release-bump` task below)
# ---------------------------------------------------------------------------


def _git(c, cmd, **kwargs):
    """Run a git command at the repo root and return the stdout."""
    return c.run(f"git -C {REPO_ROOT} {cmd}", hide=True, **kwargs)


def _current_branch(c):
    return _git(c, "rev-parse --abbrev-ref HEAD").stdout.strip()


def _working_tree_dirty(c):
    result = _git(c, "status --porcelain")
    return bool(result.stdout.strip())


def _read_pyproject_version():
    """Return the version string in packages/naas/pyproject.toml."""
    import tomllib

    with PYPROJECT_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _write_pyproject_version(new_version):
    """Update the version line in packages/naas/pyproject.toml in place.

    Uses a regex anchored to the start of the line and the [project]
    section to avoid touching unrelated `version = "..."` strings.
    """
    text = PYPROJECT_PATH.read_text()
    new_text = re.sub(
        r'^version = ".*?"$',
        f'version = "{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_text == text:
        raise RuntimeError(f"Could not find a version line to update in {PYPROJECT_PATH}")
    PYPROJECT_PATH.write_text(new_text)


def _validate_target_version(current, target, branch):
    """Raise SystemExit with a clear message if target is invalid.

    Checks performed:
    * target matches the release-version regex (rejects alphas and garbage)
    * target's major.minor matches the branch's major.minor
    * target is strictly greater than current per PEP 440
    """
    from packaging.version import InvalidVersion, Version

    target_match = RELEASE_VERSION_RE.match(target)
    if not target_match:
        raise SystemExit(
            f"❌ Target version '{target}' is not a valid release version.\n"
            "   Allowed shapes: X.Y.Z, X.Y.ZbN, X.Y.ZrcN.\n"
            "   Alphas (X.Y.ZaN) are not released — they live on develop only."
        )

    branch_match = RELEASE_BRANCH_RE.match(branch)
    if not branch_match:
        raise SystemExit(
            f"❌ Current branch '{branch}' is not a release branch.\n"
            "   Expected something matching release/X.Y (e.g. release/1.3)."
        )

    target_major, target_minor = target_match.group(1), target_match.group(2)
    branch_major, branch_minor = branch_match.group(1), branch_match.group(2)
    if (target_major, target_minor) != (branch_major, branch_minor):
        raise SystemExit(
            f"❌ Target version {target} does not match branch {branch}.\n"
            f"   Branch tracks release/{branch_major}.{branch_minor}; bump only "
            f"{branch_major}.{branch_minor}.* versions on this branch."
        )

    try:
        current_v = Version(current)
        target_v = Version(target)
    except InvalidVersion as exc:
        raise SystemExit(f"❌ Could not parse versions: {exc}") from exc

    if target_v <= current_v:
        raise SystemExit(f"❌ Target version {target} must be strictly greater than current {current}.")


def _list_fragment_files():
    """Return a sorted list of fragment file Paths under packages/naas/changes/.

    A fragment is any .md file in the directory other than the towncrier
    template. Hidden files (starting with `.`) are also ignored.
    """
    if not CHANGES_DIR.is_dir():
        return []
    return sorted(p for p in CHANGES_DIR.glob("*.md") if p.name != "template.md.j2" and not p.name.startswith("."))


def _is_final_release(target):
    """True for X.Y.Z (no prerelease suffix), False for b/rc."""
    return RELEASE_VERSION_RE.match(target).group(4) is None


def _print_step(label, message):
    print(f"  [{label}] {message}", file=sys.stderr)


@task(
    help={
        "version": (
            "Target version to release (e.g. 1.3.0b1, 1.3.0rc2, 1.3.0, 1.3.1). "
            "Must match the major.minor of the current release/X.Y branch."
        ),
        "dry-run": "Print every action without executing.",
        "no-push": "Run all local steps (commit, tag) but skip the push.",
        "message": (
            "Override the commit message. Default: 'chore(release): release X.Y.Z' "
            "for finals or 'chore(release): bump version to X.Y.ZbN/rcN' for prereleases."
        ),
    }
)
def release_bump(c, version, dry_run=False, no_push=False, message=""):
    """Run the release ceremony for the current release/X.Y branch.

    What this does, in order:

    1. Validate the working tree is clean and we are on a release/X.Y branch.
    2. Validate the target version is compatible with the current branch
       and strictly newer than the current pyproject.toml version.
    3. For final releases (no b/rc suffix): require at least one towncrier
       fragment to exist in packages/naas/changes/.
    4. Update packages/naas/pyproject.toml with the new version.
    5. Run `uv lock` to refresh the lockfile.
    6. For final releases: pin the k8s manifest image tags to the new version,
       then run `towncrier build --yes` to append a section to CHANGELOG.md
       and delete consumed fragments.
    7. Stage everything that changed, commit with a conventional release
       message, and create an annotated tag at the new commit.
    8. Push branch and tag atomically (`git push --atomic`).

    Use --dry-run for a first pass without touching anything.
    Use --no-push to keep the local commit and tag without pushing,
    e.g. for inspection before the push.
    """
    # ----- Pre-flight checks -----
    branch = _current_branch(c)
    if not RELEASE_BRANCH_RE.match(branch):
        raise SystemExit(f"❌ release-bump can only run on a release/X.Y branch.\n   You are currently on '{branch}'.")

    if _working_tree_dirty(c):
        raise SystemExit("❌ Working tree is dirty. Commit or stash your changes first.")

    # Confirm we are not behind the remote — if we are, the human's bump
    # commit might land on top of the wrong base.
    _git(c, "fetch origin")
    behind = _git(c, f"rev-list --count HEAD..origin/{branch}").stdout.strip()
    if behind != "0":
        raise SystemExit(
            f"❌ Local branch is behind origin/{branch} by {behind} commit(s).\n"
            f"   Run `git pull --ff-only origin {branch}` first."
        )

    current_version = _read_pyproject_version()
    _validate_target_version(current_version, version, branch)

    is_final = _is_final_release(version)
    if is_final:
        fragments = _list_fragment_files()
        if not fragments:
            raise SystemExit(
                "❌ Cannot release a final version with no changelog fragments.\n"
                f"   Add at least one fragment to {CHANGES_DIR.relative_to(REPO_ROOT)} "
                "before running this task."
            )

    # ----- Decide on commit message and tag -----
    tag = f"v{version}"
    if not message:
        if is_final:
            message = f"chore(release): release {version}"
        else:
            message = f"chore(release): bump version to {version}"

    print(f"\n🚀 Releasing {tag} on {branch} (current pyproject.toml version: {current_version})\n")

    # ----- Step executor that respects --dry-run -----
    def run(label, cmd, **kwargs):
        _print_step(label, cmd)
        if dry_run:
            return None
        return c.run(cmd, **kwargs)

    # ----- 4. Update pyproject.toml -----
    _print_step("edit", f"set pyproject.toml version → {version}")
    if not dry_run:
        _write_pyproject_version(version)

    # ----- 5. uv lock -----
    run("lock", "uv lock", pty=False)

    # ----- 6. Final-release specific steps -----
    if is_final:
        for manifest in (K8S_API_DEPLOYMENT, K8S_WORKER_DEPLOYMENT):
            # Use the absolute path so the command works regardless of cwd
            # (the documented invocation runs invoke from packages/naas/).
            run(
                "k8s",
                (f"sed -i 's|ghcr.io/lykinsbd/naas:.*|ghcr.io/lykinsbd/naas:{version}|g' {manifest}"),
            )
        # towncrier needs to run from the directory holding pyproject.toml
        # with its [tool.towncrier] config (packages/naas/).
        run(
            "towncrier",
            f"towncrier build --yes --version {version} --dir packages/naas",
        )

    # ----- 7. Stage + commit + tag -----
    paths_to_add = [
        "packages/naas/pyproject.toml",
        "uv.lock",
    ]
    if is_final:
        paths_to_add.extend(
            [
                "CHANGELOG.md",
                "k8s/api/deployment.yaml",
                "k8s/worker/deployment.yaml",
                "packages/naas/changes/",
            ]
        )

    run("add", f"git -C {REPO_ROOT} add -- {' '.join(paths_to_add)}")
    # Use shell-safe single quotes; release messages never contain single
    # quotes in our convention, but defend anyway.
    safe_message = message.replace("'", "'\\''")
    run("commit", f"git -C {REPO_ROOT} commit -m '{safe_message}'")
    run(
        "tag",
        f"git -C {REPO_ROOT} tag -a -m 'Release {tag}' {tag}",
    )

    # ----- 8. Push (or not) -----
    if no_push:
        print(
            f"\n✋ --no-push set. Local commit and tag {tag} are ready.\n"
            f"   Push with:  git push --atomic origin {branch} {tag}\n"
        )
        return

    run(
        "push",
        f"git -C {REPO_ROOT} push --atomic origin {branch} {tag}",
    )

    if dry_run:
        print("\n💡 Dry run complete. No changes were made. Run again without --dry-run to apply.\n")
    else:
        print(f"\n✅ Released {tag}. CI will create the GitHub Release.\n")
