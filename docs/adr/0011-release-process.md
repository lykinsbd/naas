# ADR 0011: Release branch as the source of truth during a release

* Status: Accepted
* Date: 2026-05-19

## Context and Problem Statement

NAAS uses long-lived release branches (`release/X.Y`) for maintenance and a `develop` → `release/X.Y` → `main` flow for new releases. The release pipeline that grew up around this branching model spread state across multiple branches and relied on CI committing changelog and version-bump artifacts back to whichever branch triggered the workflow. Over the v2.1.0 release cycle this caused several distinct failures:

* `release/2.1` diverged from `main` after a rebase merge because `release.yml` had committed changelog regenerations to `release/2.1` that were not part of the rebased commits on `main`. Required a manual `-X theirs` merge to recover.
* `release.yml` re-fired on a `pyproject.toml` change after the tag already existed and pushed a stale changelog commit before failing on the duplicate tag.
* `CHANGELOG.md` accumulated drift over time: entries for `v1.0.0b3`, `v1.3.0`, and most of `v1.4.0` were either missing or wrong, because CI regenerated the file from depleted fragments after rebase merges with non-idempotent inputs.
* The `finalize-release.yml` workflow opened a separate PR on `main` to bump from `rcN` to the final version, creating a state machine that straddled both `release/X.Y` and `main`.
* `delete_branch_on_merge=true` deleted `release/X.Y` branches on merge to `main` (resolved separately by a repository ruleset, but indicative of the friction).

A normal release required 5+ PRs, multiple manual interventions, and several "what state are we in?" moments.

The root cause shared by all of these is **the release pipeline used commits to `pyproject.toml` as the trigger and committed back to whichever branch fired the workflow**. The release became a cross-branch state machine rather than a single ceremony.

## Decision Drivers

* The release process should be possible to reason about without consulting CI logs
* CI should not commit to branches — every change to a branch should come from a reviewable human action
* `CHANGELOG.md` should have one source of truth and stay accurate over time
* Long-lived release branches must remain viable for hotfixes (the model that motivated `release/X.Y` in the first place)
* Rebase merges of release PRs should not break subsequent automation
* The release ceremony should reduce to "bump version, push tag" — anything else is incidental
* Conventional Commits compatibility should be preserved for ordinary feature work

## Considered Options

* **Option 1**: Keep the current model and patch incrementally
* **Option 2**: Adopt [release-please](https://github.com/googleapis/release-please) (Google's commit-driven release-PR tool)
* **Option 3**: Tag-driven release with a single `release/X.Y` branch as source of truth during a release (chosen)

## Decision Outcome

Chosen option: **Option 3 — release branch is the truth during a release; CI never commits back; the human runs `inv release-bump VERSION` to do the entire ceremony in one command**.

### Branching model

| Branch | Purpose | Lifetime |
| --- | --- | --- |
| `develop` | Active development; alpha versions only (`X.Y.0aN`) | Permanent |
| `release/X.Y` | All work for the X.Y line — beta/RC/final, plus all X.Y.Z hotfixes | Permanent (kept forever, protected by repo ruleset) |
| `main` | Record of what was released, in chronological order | Permanent |
| `feature/`, `fix/`, `hotfix/`, `chore/`, etc. | Ordinary work | Short-lived; auto-deleted on merge |

### Release flow (new minor: X.Y.0)

```text
1.  git checkout develop && git pull
2.  git checkout -b release/X.Y && git push -u origin release/X.Y
3.  inv release-bump X.Y.0b1
      → bumps pyproject.toml
      → runs uv lock
      → commits "chore(release): bump version to X.Y.0b1"
      → creates annotated tag vX.Y.0b1
      → git push --atomic origin release/X.Y vX.Y.0b1
4.  release.yml fires on the tag push → creates GitHub prerelease
5.  Test, fix bugs via PR back to release/X.Y, repeat for rcN as needed
6.  inv release-bump X.Y.0
      → bumps pyproject.toml
      → runs uv lock
      → runs `towncrier build --yes` (appends section to CHANGELOG.md, deletes consumed fragments)
      → commits "chore(release): release X.Y.0"
      → creates tag vX.Y.0
      → git push --atomic origin release/X.Y vX.Y.0
7.  release.yml fires on the tag push → creates GitHub release with body extracted from CHANGELOG.md
8.  Tag push triggers sync-release.yml → opens main → develop sync PR + develop bump PR
9.  Open release/X.Y → main PR, merge with merge-commit (preserves the tag SHAs in main's history)
10. Merge the auto-created sync and bump PRs
```

The new minor release is two human PR merges: `release/X.Y → main`, then `main → develop` (plus the develop alpha-bump PR).

### Hotfix flow (X.Y.Z, Z > 0)

```text
1.  git checkout release/X.Y && git pull
2.  git checkout -b hotfix/issue-description
3.  Fix + add changelog fragment, PR to release/X.Y, merge
4.  git checkout release/X.Y && git pull
5.  inv release-bump X.Y.Z
6.  release.yml fires → final release on release/X.Y
7.  sync-release.yml opens main → develop PR
8.  Open release/X.Y → main PR, merge with merge-commit
```

### Tag location and merge strategy

* Tags are created at the SHA on `release/X.Y` by the `inv release-bump` task, immediately before push
* The push uses `git push --atomic origin release/X.Y vX.Y.Z` so the commit and tag land together or neither does
* Release PRs into `main` use **merge-commit** (not rebase or squash). This preserves the tagged SHA from `release/X.Y` as a real ancestor of `main`. The merge commit itself becomes the "we shipped X.Y.Z" event in `main`'s history.
* Ordinary PRs (feature, fix, hotfix into release/X.Y, develop sync PRs) can use whatever merge strategy fits — typically rebase or squash for linear history

### CHANGELOG.md ownership

* `CHANGELOG.md` at the repo root is the single source of truth
* Humans append release sections via `towncrier build --yes` invoked through `inv release-bump`
* CI never modifies `CHANGELOG.md`
* Docs site renders from `CHANGELOG.md` via `mkdocs-include-markdown-plugin` transclusion (one file, two views)
* `release.yml` extracts the just-added section from `CHANGELOG.md` to use as the GitHub Release body

### What `release.yml` does and only does

* Triggered only by tag pushes matching `v*`
* Validates the tag matches a release version regex (refuses `vfoo`)
* Reads the version from the tag
* Extracts the corresponding section from `CHANGELOG.md`
* Creates a GitHub Release (prerelease for `bN`/`rcN`, full release for `X.Y.Z`)
* Attaches release artifacts (Postman collection, OpenAPI spec)
* **Does not** generate `CHANGELOG.md`. Does not commit to any branch. Does not push tags.

### Workflows that go away

* `finalize-release.yml` is deleted. The rcN → final bump becomes a human action via `inv release-bump X.Y.0` on `release/X.Y`.

### Workflows that change

* `release.yml`: trigger changes from `push: paths: pyproject.toml` to `push: tags: 'v*'`. All commit-back logic removed.
* `sync-release.yml`: drops the `sync-to-release-branch` job (no longer needed; merge-commit makes it trivial). The `bump-develop` job is fixed to skip patch releases (X.Y.Z, Z > 0), which today's behavior gets wrong.

### Consequences

* Good: Single ceremony command (`inv release-bump VERSION`) instead of multiple manual steps spread across branches
* Good: `CHANGELOG.md` becomes authoritative and stays accurate (every entry is a reviewed human commit)
* Good: Release PRs and tag SHAs are reachable from `main` via merge commits — no rebase divergence
* Good: 2 PRs in a normal release (release/X.Y → main, main → develop) instead of 5+
* Good: Eliminates the entire class of "CI committed back to a branch and now branches diverge" bugs
* Good: Tag-driven trigger means `pyproject.toml` edits unrelated to release no longer fire `release.yml`
* Good: `release/X.Y` history remains coherent (no CI commits interleaved with human work)
* Bad: Humans must remember to bump versions and push tags. Mitigated by `inv release-bump` doing both atomically in one command and by validation in the task (refuses inconsistent version transitions).
* Bad: Patch releases on `release/X.Y` will not always be ancestor-reachable from `main` if multiple hotfixes happen out of order. Acceptable trade-off; merge-commit preserves the tag SHAs in `main` regardless of order.
* Bad: A malicious or accidental tag push could trigger `release.yml`. Mitigated by tag-format regex validation in the workflow and by branch protection on who can push.

## Pros and Cons of the Options

### Option 1: Keep the current model, patch incrementally

* Good: No design change required; each followup is a small fix
* Good: Existing release flow is documented and known
* Bad: Doesn't address the structural cause — CI committing back to branches and a state machine spread across release/X.Y and main
* Bad: Each fix patches a symptom; the next bug from the same root cause is just a matter of time
* Bad: Five of the six release issues during the v2.1.0 cycle traced to this same root cause

### Option 2: release-please (Google)

* Good: Industry-standard tool, very well documented
* Good: Eliminates the "commit-back-as-trigger" coupling — the trigger becomes "merge a release PR"
* Good: Native monorepo support
* Bad: Requires conventional commits to drive versioning (becomes load-bearing rather than convention)
* Bad: Built around a single-mainline trunk-based model. Adapting to develop/release/X.Y/main is awkward.
* Bad: Doesn't natively understand towncrier; would either replace towncrier (losing per-PR fragment review) or layer awkwardly
* Bad: Beta/RC support exists but is less natural than the prerelease-on-release-branch pattern NAAS uses
* Bad: Significant rework of branching, changelog approach, and release ceremony

### Option 3: Release branch as truth, tag-driven, human-orchestrated

* Good: Solves all the structural issues (commit-back, divergence, state across branches)
* Good: Aligns with how Linux kernel, kubernetes, PostgreSQL, and most maintenance-branch projects structure releases
* Good: Towncrier stays as designed — fragments per PR, consumed at release time
* Good: Two PRs in a normal release; one human ceremony command
* Good: Doesn't impose a commit-message convention on contributors
* Good: ADR-able — the design fits in one document
* Bad: Requires a more disciplined release ceremony (pull, bump, push) than "merge a PR and walk away"
* Bad: Some edge cases (concurrent hotfixes, forgotten fragments) remain operator concerns

## Implementation

* `inv release-bump VERSION` invoke task — added to `packages/naas/tasks.py`
* `release.yml` — rewritten: trigger on tag push, no commit-back
* `finalize-release.yml` — deleted
* `sync-release.yml` — drop `sync-to-release-branch` job, fix patch-release develop-bump bug
* `docs/development.md` — release process section rewritten to match
* `.kiro/agents/naas-dev-prompt.md` — branching strategy and release sections updated

Tracked in #480.

## References

* Issue #468 — release.yml's tag-exists check (early symptom of commit-back-as-trigger)
* Issue #469 — historical release branches deleted (auto-delete + commit-back interaction)
* Issue #471 — release branches auto-deleted (resolved separately by repo ruleset)
* Issue #466 — manual `release/2.1` divergence cleanup (rebase merge vs commit-back)
* PR #466 — first occurrence of the "merge main into release/X.Y with -X theirs" recovery pattern
* Issue #477 — backfilled CHANGELOG.md entries (foundation for "humans own this file")
* Issue #478 — transcluded CHANGELOG.md into the docs site (single source of truth)
* Issue #480 — implementation of this ADR
