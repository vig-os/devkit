---
type: issue
state: closed
created: 2026-08-11T11:38:38Z
updated: 2026-08-11T11:54:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1421
comments: 1
labels: chore, semver:major
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:05.872Z
---

# [Issue 1421]: [[CHORE] Remove the scaffolded devc-upgrade recipe; point version-check at the adoption-PR flow](https://github.com/vig-os/devkit/issues/1421)

## Description

Remove the scaffolded `devc-upgrade` recipe entirely. Since the `devkit-upgrade` workflow (self-polling adoption PRs) became the upgrade path, the recipe's every use is covered better elsewhere: release adoption by the workflow's reviewed PR, managed-file repair by plain git (the rendered files are committed; the scaffold-drift gate detects divergence), and manual/emergency re-scaffolds by the documented `curl … install.sh | bash -s -- --force .` one-liner the recipe merely wraps. Meanwhile the `version-check.sh` notification actively steers users at `just devc-upgrade`, routing them around the PR-reviewed adoption flow and inviting local force-upgrades that compete with an open adoption PR — and the "devc" name is a devcontainer-era leftover.

Scope:

- `assets/workspace/.devcontainer/justfile.devc`: delete the `devc-upgrade` recipe (no tombstone stub — clean removal).
- `assets/workspace/.devcontainer/scripts/version-check.sh`: rewrite the update notification — when `.github/workflows/devkit-upgrade.yml` exists in the repo, point at the adoption-PR flow; otherwise give the `install.sh --force` one-liner. Never mention the removed recipe.
- `docs/MIGRATION.md`: replace the `just devc-upgrade` mention with the one-liner.
- Tests: drop the `devc-upgrade` bats coverage in `tests/bats/just.bats`; update the `TestVersionCheckScaffold` pins in `tests/test_integration.py` (and the one `init-workspace.bats` reference) to the new notification contract — notification changes written test-first.
- `CHANGELOG.md` `Unreleased` → `Removed` entry (+ manifest-synced copy).

## Acceptance Criteria

- [ ] No live reference to `devc-upgrade` remains outside historical archives (`docs/issues/`, `docs/pull-requests/`, released changelog entries).
- [ ] `version-check.sh` notification names the adoption-PR flow when the workflow is present and the one-liner otherwise; pinned by tests.
- [ ] All affected suites green; full hook suite green.

## Related Issues

Refs: #1413 (audit), #1418 (added the now-moot behavioral tests)

## Changelog Category

Removed — breaking for consumers who script the recipe (semver:major).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 11:54 AM_

Implemented in PR #1422 (merged to dev @b078c3ec): devc-upgrade recipe deleted from the scaffold (no stub); version-check.sh notification now points automation-wired repos at the devkit-upgrade adoption-PR flow and falls back to the install.sh --force one-liner (correct advice during gitflow cron dormancy too); MIGRATION.md updated; tombstone + notification-contract tests pin the removal; Removed changelog entry (semver:major). Ships at the next release.

