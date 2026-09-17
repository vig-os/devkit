---
type: issue
state: closed
created: 2026-09-14T09:58:30Z
updated: 2026-09-14T14:28:25Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1627
comments: 2
labels: feature, area:workflow, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-15T07:34:12.929Z
---

# [Issue 1627]: [[FEATURE] prepare-release: refuse while a hotfix release branch is in flight](https://github.com/vig-os/devkit/issues/1627)

### Description

Make `prepare-release.yml` refuse to cut a regular train while any other `release/*` branch exists — the symmetric counterpart of the single-train policy `prepare-hotfix.yml` enforces (#1621, #1623).

### Problem Statement

`prepare-hotfix.yml` refuses when another `release/*` branch exists, so a hotfix cannot be cut alongside a regular train. The reverse is unguarded: a regular train can be cut from `dev` while a hotfix branch exists. That train predates the fix, so promoting it after the hotfix silently reintroduces the regression, and if it promotes first the hotfix walks `:latest` backwards (runbook rules (i)/(ii) in #1621).

### Proposed Solution

In `prepare-release.yml`'s `validate` job, after the existing "release branch does not exist" check: enumerate `refs/remotes/origin/release/*` and fail with the list when any exists (same message shape as the hotfix lane: promote or abandon it first). Applies to devkit's copy and the scaffold copy; the check is branch-name based, so it survives the trunk render unchanged.

### Alternatives Considered

- Cherry-pick obligation as a runbook rule — the failure mode is silent, so a hard refusal is safer for a solo-maintainer org (same reasoning as #1621 question 2).
- Guarding only at promote time — catches the `:latest` hazard but not the reintroduced regression.

### Additional Context

Identified while implementing #1621 (see the plan's follow-ups and the closing comment). Pairs with the promote `:latest` guard issue.

### Impact

- **Who benefits:** devkit maintainers and consumers.
- **Compatibility:** stricter prepare; a second concurrent regular train was never a supported state.

### Acceptance Criteria

- [ ] `prepare-release.yml` validate fails when any other `release/*` branch exists, in both copies
- [ ] Shape test in `tests/test_workflow_model.py` / `test_workflow_prepare_extension.py` family, trunk render included
- [ ] RELEASE_CYCLE.md updated (Phase 1 prerequisites, hotfix runbook rule)
- [ ] TDD compliance (see .claude/skills/tdd/SKILL.md)

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 12:26 PM_

## Implementation Plan

Branch: `feature/1627-prepare-release-single-train` (off `dev`). First of three PRs (#1627 → #1626 → #1625); all ship in the next regular train.

State at planning time: no `release/*` branch exists on the remote (1.14.1 promoted 2026-09-14 09:18 UTC, sync #1624 merged).

### Design

- New `validate` step **Verify no other release train is in flight**, placed directly after `Verify release branch does not exist`, in both copies of `prepare-release.yml`. Same enumeration and message shape as `prepare-hotfix.yml` ("Another release train is in flight … Promote or abandon it first (just promote-release / just abandon-release), then retry").
- Devkit copy enumerates `refs/remotes/origin/release/` (its checkout is `fetch-depth: 0`, like the existing remote check). Scaffold copy uses its own dialect, `git ls-remote --heads origin 'release/*'`, consistent with its existing branch/tag checks.
- Branch-name based only, so the trunk render is unchanged and needs no special casing.

### Tasks (one commit each, `Refs: #1627`)

1. `test:` shape test in `tests/test_workflow_prepare_extension.py` (parametrized over both copies + the `cached_tree("trunk")` render): the step exists after the branch-exists check, its `run:` enumerates `release/` refs and carries the message shape. RED.
2. `feat:` devkit `.github/workflows/prepare-release.yml`. GREEN for that copy.
3. `feat:` scaffold `assets/workspace/.github/workflows/prepare-release.yml`. GREEN for all.
4. `docs:` `docs/RELEASE_CYCLE.md` — Phase 1 prerequisites gain "no other `release/*` branch"; hotfix runbook rule rewritten (prepare direction now enforced; `:latest` ordering guard is #1626). `CHANGELOG.md` Unreleased → Added.

Verification: `uv run pytest tests/test_workflow_prepare_extension.py tests/test_workflow_model.py tests/test_workflow_prepare_hotfix.py`, `prek run --all-files` green, actionlint on both files.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 14, 2026 at 02:28 PM_

Shipped in #1630 (merged to `dev` 2026-09-14). The `validate` job of `prepare-release.yml` (devkit and scaffold copies, trunk render included) now fails, listing the offenders, when any other `release/*` branch exists on the remote — the symmetric counterpart of the hotfix lane's refusal. Consumers pick it up with the next devkit release via `devkit-upgrade`. Entry is in the Unreleased changelog section.

