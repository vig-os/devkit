---
type: issue
state: closed
created: 2026-08-10T13:40:17Z
updated: 2026-08-10T14:15:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1404
comments: 1
labels: feature, priority:medium, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:25.584Z
---

# [Issue 1404]: [feat: changelog entries for devkit adoption PRs via the renovate-changelog pair](https://github.com/vig-os/devkit/issues/1404)

## Problem

Adoption PRs opened by the devkit-upgrade workflow (#1296) do not get a `CHANGELOG.md` entry, while Renovate dependency PRs do (via the `renovate-changelog-build.yml` → `renovate-changelog-commit.yml` pair, #506/#562). The maintainer has been writing adoption entries by hand (e.g. vig-os/commit-action#125, #133). A devkit upgrade is a user-visible change and should be documented under `## Unreleased` → `### Changed` automatically, same as Renovate updates.

## Design (option B — widen the existing pair)

Reuse the Renovate changelog pipeline unchanged; only the build-side filter and the CLI grow:

- **`vig-utils` (`renovate_changelog_pr.py`)**: detect an adoption PR from its title (`chore: adopt devkit X.Y.Z[-rcN]`) before falling through to the Renovate parser. Format the entry as
  `- **Adopt vigOS devkit X.Y.Z** ([#PR](…/pull/PR)) — [release notes](https://github.com/vig-os/devkit/releases/tag/X.Y.Z)`
  and insert it via the existing `insert_renovate_changelog_entry` helper (top of `### Changed`, dedup on `[#PR](`). Spike-proven against commit-action's real changelog: clean insert, idempotent re-run, rc titles parse.
- **`renovate-changelog-build.yml`** (scaffold + devkit's own copy): widen the author filter from `renovate[bot]` to also accept `vigos-devkit-upgrade[bot]`; update the docstring. Workflow names stay unchanged (renaming a `workflow_run`-referenced workflow has a default-branch transition hazard).
- **`renovate-changelog-commit.yml`**: generalize the commit-message wording (`… for renovate PR N` → `… for PR N`); pipeline otherwise untouched.
- **Robustness**: the CLI gracefully no-ops when `CHANGELOG.md` is absent (latent crash today for any consumer shipping the pair without a changelog).

## Properties

- PR number is naturally available (the pair reacts to the PR), so no dependency on the adoption issue — pairs with the follow-up that removes it.
- `pull_request` workflows run from the PR head, so the adoption PR that ships this change already gets its own entry.
- rc → final force-updates wipe the changelog commit, but the `synchronize` event re-triggers the pair (sender guard only excludes `commit-action-bot[bot]`), which re-adds the entry with the new version — self-healing.
- Always-on wherever the pair is scaffolded (Renovate parity, no new `.vig-os` knob); trunk repos without the `renovate` feature group / changelog are a no-op.

## Acceptance criteria

- [ ] Unit tests: adoption-title parsing (final + rc), entry formatting, insertion under `### Changed`, dedup, missing-changelog no-op, Renovate path regression-free
- [ ] Scaffold + devkit-own build workflows accept `vigos-devkit-upgrade[bot]`; commit workflow wording generalized
- [ ] `CHANGELOG.md` Unreleased entry
---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 02:15 PM_

Shipped to dev via PR #1407 (merge commit 46178bb5, auto-merged green 2026-08-10). `renovate-changelog-pr` now branches on the `chore: adopt devkit X.Y.Z[-rcN]` title and inserts the adoption entry under `## Unreleased` → `### Changed` (PR link + devkit release-notes link, dedup on the PR link), no-ops when a consumer has no `CHANGELOG.md`, and the scaffolded `renovate-changelog-build.yml` accepts `vigos-devkit-upgrade[bot]`. Because the build workflow runs from the PR head, entries go live from the very adoption PR that ships this release. Closing manually — dev-targeted PRs don't auto-close.

