---
type: issue
state: closed
created: 2026-09-14T09:58:08Z
updated: 2026-09-14T14:38:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1625
comments: 2
labels: feature, area:workspace, area:workflow, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-15T07:34:13.682Z
---

# [Issue 1625]: [[FEATURE] Port the hotfix release lane to the workspace scaffold (copy-exclude under trunk)](https://github.com/vig-os/devkit/issues/1625)

### Description

Phase 2 of #1621: ship `prepare-hotfix.yml` in `assets/workspace/.github/workflows/` so gitflow consumers get the same lane devkit now has (#1623). Wired as **copy-exclude under `DEVKIT_WORKFLOW=trunk`** (trunk releases already cut from `main`, so the lane is redundant there — same mechanism as `sync-main-to-dev.yml`) and added to the `release` feature group (solo adopters unaffected by construction).

### Problem Statement

Devkit's own train and the consumer train are parallel implementations, so #1623 proved the choreography in devkit only. A consumer hitting an urgent fix while `dev` is ahead still has no supported lane. `workflow_dispatch` only works once the file is on the consumer's default branch and adoption PRs merge to `dev`, so a consumer cannot adopt-and-use in the same emergency: ship before it is needed.

### Proposed Solution

- Add the scaffold copy of `prepare-hotfix.yml` (scaffold-shaped: the reusable `prepare-release-extension.yml` hook stays the only project-specific seam; no `uv run`, toolchain via `setup-devkit-toolchain` as in the scaffold `prepare-release.yml`).
- `scripts/manifest.toml`: copy-exclude the file under `DEVKIT_WORKFLOW=trunk`; add it to the `release` feature group; **drop the `RemoveBlock` transform** that currently strips `just prepare-hotfix` from the scaffolded `justfile.gh`.
- `zizmor.yml` (root + scaffold): baseline entries for the managed basename where required (`github-app`; `artipacked` should not be needed — every checkout sets `persist-credentials: false`).
- Tests: extend `tests/test_workflow_prepare_hotfix.py` to both copies; `tests/test_workflow_model.py` pins the trunk exclusion; flip the scaffold-leak guard; `tests/test_workflow_zizmor_baseline.py` covers the baseline.
- `docs/DOWNSTREAM_RELEASE.md` and `docs/MIGRATION.md`: consumer-facing section.
- Validate on `devkit-smoke-test` via the existing cross-repo gate harness — only possible after a devkit release ships the asset.

### Alternatives Considered

- Offering trunk repos the content-free lane too — rejected in #1621 (redundant; trunk already cuts from `main`).
- Keeping the lane devkit-only — leaves consumers without a supported emergency path.

### Additional Context

Design and decisions: #1621 (plan comment), #1623. The scaffold's `release-core.yml` (validate job, "Verify CHANGELOG has TBD entry", line ~210) still greps for the bare heading; it must switch to `prepare-changelog validate --version` like devkit's `release.yml` did in #1623, or a seeded-but-unfilled hotfix section could ship downstream.

### Impact

- **Who benefits:** all gitflow consumers.
- **Compatibility:** additive; new managed workflow file plus a recipe that was previously stripped.

### Acceptance Criteria

- [ ] Scaffolded gitflow workspace contains `prepare-hotfix.yml`; trunk workspace does not
- [ ] `just prepare-hotfix` present in the scaffolded `justfile.gh`
- [ ] zizmor over the managed set is clean against the shipped baseline
- [ ] Smoke-test rehearsal on `devkit-smoke-test` (prepare → fix PR → candidate → abandon)
- [ ] TDD compliance (see .claude/skills/tdd/SKILL.md)

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 12:26 PM_

## Implementation Plan

Branch: `feature/1625-scaffold-hotfix-lane` (off `dev`), after #1627 and #1626.

### Corrections to the issue text (from the code)

- The trunk copy-exclude and the `release` feature group live in `assets/init-workspace.sh`, not `scripts/manifest.toml` (only the `RemoveBlock` is there). `sync-main-to-dev.yml` is special-cased in five places (preview classifier, upgrade DELETIONS, rsync exclude, post-copy prune, preserved-class carve-out) plus `feature_paths()`. Plan: generalise to a `TRUNK_EXCLUDED_WORKFLOWS` list instead of a sixth copy.
- The scaffold-leak guard is `tests/test_workflow_prepare_hotfix.py::test_scaffold_justfile_does_not_leak_prepare_hotfix`, not in `test_workflow_model.py`; it gets inverted.
- zizmor baseline needs `github-app` **and** `secrets-inherit` (the lane uses `secrets: inherit`); `artipacked` is not needed. Entries must land in the same commit as the scaffold file (`test_workflow_zizmor_baseline` requires every basename to exist under `assets/workspace/`).
- The scaffold's host-side validate jobs have no CLI, but hotfix validate needs `prepare-changelog` (empty-Unreleased refusal, seed probe). The port mirrors the scaffold `promote-release.yml` shape: `resolve-toolchain` job → validate in the toolchain container.

### Tasks (`Refs: #1625`)

1. `test:` extend `tests/test_workflow_prepare_hotfix.py` to both copies (`both_copies()`), add the scaffold lane to `CALLER_WORKFLOWS`, pin gitflow-has / trunk-lacks `prepare-hotfix.yml` and the upgrade prune in `tests/test_workflow_model.py`, invert the leak guard, cover the baseline, and pin `release-core.yml`'s TBD step on `prepare-changelog validate --version`. RED.
2. `feat:` `assets/workspace/.github/workflows/prepare-hotfix.yml` (scaffold dialect: no `uv run`, `resolve-toolchain` + `setup-devkit-toolchain`, `TAG_PREFIX`-aware tag checks like scaffold `prepare-release.yml`, `prepare-release-extension.yml` hook, `persist-credentials: false` everywhere) + `zizmor.yml` root and scaffold entries and header prose.
3. `feat:` `init-workspace.sh` trunk-exclude generalisation + `release` group entry; `manifest.toml` drops the `RemoveBlock`; `sync_manifest.py sync`.
4. `feat:` scaffold `release-core.yml` validate: `Verify CHANGELOG has TBD entry` → `prepare-changelog validate --version "$VERSION"` (vig-utils with `--version` ships in the same devkit release as this workflow, so the toolchain contract holds).
5. `docs:` `DOWNSTREAM_RELEASE.md` (overview list, workflow-models trunk carve-out, workflow interface), `MIGRATION.md` (workflow lists, trunk render, `release` group), `RELEASE_CYCLE.md` consumer-scaffold paragraph; `CHANGELOG.md`.

Post-merge: after the next devkit release ships and `devkit-upgrade` adopts it on `devkit-smoke-test`, run the rehearsal (prepare-hotfix → fix PR → publish-candidate → abandon-release). Devkit's own Layer 2 rehearsal (#1621) can share that window.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 14, 2026 at 02:38 PM_

Shipped in #1632 → #1631 (merged to `dev` 2026-09-14).

- `assets/workspace/.github/workflows/prepare-hotfix.yml` in the scaffold dialect (`resolve-toolchain` + `setup-devkit-toolchain`, `DEVKIT_TAG_PREFIX`-aware, `persist-credentials: false` everywhere, `prepare-release-extension.yml` as the only seam); `just prepare-hotfix X.Y.Z` now ships in the scaffolded `justfile.gh` (the `RemoveBlock` is gone).
- Gitflow only: copy-excluded under `DEVKIT_WORKFLOW=trunk` and pruned on a gitflow → trunk upgrade via the new shared `TRUNK_EXCLUDED_WORKFLOWS` list in `init-workspace.sh`; part of the `release` feature group.
- Scaffold `release-core.yml` gates on `prepare-changelog validate --version`, so a seeded-but-unfilled hotfix section cannot ship downstream.
- `zizmor.yml` (root + scaffold) baselines the managed basename; the renovate preset disables Renovate over it like the rest of the managed set.
- Consumer runbook in `docs/DOWNSTREAM_RELEASE.md` (Hotfix lane), `docs/MIGRATION.md` and `docs/RELEASE_CYCLE.md` updated.

Acceptance criteria met except the last runtime one, which is post-release by construction: the smoke-test rehearsal on `devkit-smoke-test` (prepare-hotfix → fix PR → publish-candidate → abandon-release) needs the next devkit release to ship the asset and `devkit-upgrade` to adopt it there. Closing as shipped; the rehearsal runs in the next release window alongside devkit's own Layer 2 rehearsal from #1621.

