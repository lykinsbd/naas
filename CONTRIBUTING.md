# Contributing to NAAS

Thank you for your interest in contributing to NAAS!

## Getting started

1. Install [uv](https://github.com/astral-sh/uv):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and set up:

   ```bash
   git clone https://github.com/lykinsbd/naas.git
   cd naas
   uv sync --extra dev
   pre-commit install
   ```

3. Run checks and tests:

   ```bash
   uv run invoke check
   uv run invoke test
   ```

## Submitting a pull request

1. Create a feature branch from `develop`
2. Make changes with [conventional commits](https://www.conventionalcommits.org/)
3. Add a changelog fragment: `uv run towncrier create <issue#>.<type>.md --content "..."`
4. Ensure `uv run invoke check` and `uv run invoke test` pass
5. Open a PR targeting `develop` and reference the related issue

PRs are merged via squash or rebase — no merge commits.

## Full development reference

See the [Development Guide](https://naas.readthedocs.io/en/latest/development/) for:

- Branching strategy and hotfix workflow
- Commit message conventions
- Code style standards
- Testing requirements
- Changelog fragment types
- Release process

## Questions

Open an issue or start a [discussion](https://github.com/lykinsbd/naas/discussions).
