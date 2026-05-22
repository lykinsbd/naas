# Contributing to NAAS

Thank you for your interest in contributing to NAAS!

## Getting started

1. Install [uv](https://github.com/astral-sh/uv):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install [mise](https://mise.jdx.dev/) for non-Python tools (currently just Vale, used by `invoke docs_check`):

   ```bash
   curl https://mise.run | sh
   ```

   Mise picks up `.mise.toml` in the repo root and installs everything pinned there. If you'd rather not use mise, see "Alternative tool install" below.

3. Clone and set up:

   ```bash
   git clone https://github.com/lykinsbd/naas.git
   cd naas
   uv sync --extra dev
   mise install   # installs Vale at the pinned version
   pre-commit install
   ```

4. Run checks and tests:

   ```bash
   uv run invoke check
   uv run invoke test
   ```

### Alternative tool install

If you don't want to use mise, install Vale yourself at the version pinned in `.mise.toml`:

- **macOS**: `brew install vale`
- **Linux**: download the matching release from [Vale's GitHub releases](https://github.com/errata-ai/vale/releases)
- **Other tool managers**: asdf and aqua both support Vale

Skipping Vale is fine for most contributions; CI will run prose-lint regardless. You only need it locally if you want `invoke docs_prose` or `invoke docs_check` to run.

## Submitting a pull request

1. Create a feature branch from `develop`
2. Make changes with [conventional commits](https://www.conventionalcommits.org/)
3. Add a changelog fragment: `uv run towncrier create <issue#>.<type>.md --content "..."`
4. Ensure `uv run invoke check` and `uv run invoke test` pass
5. Open a PR targeting `develop` and reference the related issue

PRs targeting `develop` are merged via squash or rebase to keep history linear. Release PRs into `main` (`release/X.Y` → `main`) use a merge commit so the release tag SHA stays reachable from `main`'s history — see [ADR 0011](https://naas.readthedocs.io/en/develop/adr/0011-release-process/).

## Full development reference

See the [Development Guide](https://naas.readthedocs.io/en/develop/development/) for:

- Branching strategy and hotfix workflow
- Commit message conventions
- Code style standards
- Testing requirements
- Changelog fragment types
- Release process

## Questions

Open an issue or start a [discussion](https://github.com/lykinsbd/naas/discussions).
