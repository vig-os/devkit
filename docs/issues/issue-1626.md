---
type: issue
state: closed
created: 2026-09-14T09:58:20Z
updated: 2026-09-14T14:38:16Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1626
comments: 2
labels: feature, area:workflow, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-15T07:34:13.310Z
---

# [Issue 1626]: [[FEATURE] promote-release: refuse to move :latest to a lower version](https://github.com/vig-os/devkit/issues/1626)

### Description

Add a semver guard to `promote-release.yml` (devkit copy first; scaffold copy where it moves a floating tag) that refuses to promote a version lower than the one `:latest` currently points at.

### Problem Statement

Promote moves GHCR `:latest` unconditionally. With the hotfix lane (#1621, #1623) a patch can be cut from `main` while a regular train is later cut from `dev`; if the regular train promotes first, promoting the hotfix afterwards walks `:latest` backwards. `prepare-hotfix.yml` refuses when another `release/*` exists, but `prepare-release.yml` does not refuse while a hotfix branch exists (tracked separately), so the ordering hazard is real. Today it is a runbook rule only (RELEASE_CYCLE.md, Hotfix lane).

### Proposed Solution

In `promote-release.yml`'s `validate` job: resolve the version `:latest` currently resolves to (from the image's `org.opencontainers.image.version` label / the manifest annotations, or the highest published final release), compare with `sort -V`, and fail before the irreversible publish when `VERSION` is lower. No override input unless a concrete need appears (YAGNI); the recovery is to promote in the right order or re-cut.

### Alternatives Considered

- Runbook only (status quo from #1621, question 3) — relies on memory at the most stressful moment.
- Refusing at prepare time instead — covered by the prepare-release refusal issue; both are needed because trains can be cut in either order.

### Additional Context

Discussed as open question 3 in #1621; deferred from #1623 to keep that change to a new file.

### Impact

- **Who benefits:** devkit maintainers; consumers once scaffolded.
- **Compatibility:** stricter promote; regular trains are unaffected (always higher than `:latest`).

### Acceptance Criteria

- [ ] Promote fails loudly, before publish, when `VERSION < current :latest`
- [ ] Shape/behaviour test in the `tests/test_promote_release.py` family
- [ ] RELEASE_CYCLE.md runbook rule updated to point at the guard
- [ ] TDD compliance (see .claude/skills/tdd/SKILL.md)

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 12:26 PM_

## Implementation Plan

Branch: `feature/1626-promote-latest-guard` (off `dev`), after #1627.

### Findings that shape the design

- No `org.opencontainers.image.version` label exists: the image is built by Nix `buildLayeredImage` and `flake.nix` sets only title/source/licenses. Reading GHCR package metadata needs a `packages` scope the scaffold's token does not have.
- Both `promote-release.yml` copies already page `repos/{repo}/releases` into a JSON payload in the validate step `Verify draft GitHub Release exists`. The highest published final release (draft=false, prerelease=false, bare semver after `TAG_PREFIX` strip) is derivable from that same payload — no extra API call, no new permission.
- `:latest` (devkit) and the git floating tags (scaffold, opt-in) both follow promoted versions, so "highest published final" is the value each floating ref currently points at.

### Design

- **Devkit copy**: new validate step **Verify version does not walk :latest backwards**, after the draft-release check: compute `HIGHEST` from the release list, fail when `sort -V` orders `VERSION` below `HIGHEST`. No override input (YAGNI); message: promote in order, or abandon and re-cut as the next patch of the new line.
- **Scaffold copy**: same step, gated on `needs.resolve-toolchain.outputs.floating-tags != ''` — the only floating ref the scaffold moves is the git floating tag, and consumers without floating tags keep the freedom to publish a patch for an older line.
- Equal versions cannot reach promote (the tag/release already exists), so the comparison is strictly-lower.

### Tasks (one commit each, `Refs: #1626`)

1. `test:` `tests/test_promote_release.py` — shape pins (both copies: step present before `promote`, gated as above in the scaffold) and a behavioural test that extracts the comparison script and runs it against a fake release list (lower → exit 1 with the message, higher → pass, empty list → pass, pre-releases/drafts ignored, prefixed tags stripped). RED.
2. `feat:` devkit `.github/workflows/promote-release.yml`. 
3. `feat:` scaffold `assets/workspace/.github/workflows/promote-release.yml`.
4. `docs:` `docs/RELEASE_CYCLE.md` runbook rule points at the guard; `docs/DOWNSTREAM_RELEASE.md` floating-tags note; `CHANGELOG.md`.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 14, 2026 at 02:38 PM_

Shipped in #1631 (merged to `dev` 2026-09-14).

- Devkit's `promote-release.yml` `validate` job now compares the version against the highest published final GitHub Release (the version `:latest` follows) and fails before the irreversible publish when it is lower. No override: abandon the stale train and re-cut the fix as the next patch of the published line.
- The scaffold copy carries the same guard for the opt-in git floating tags, active only when `DEVKIT_FLOATING_TAGS` is set; release tags are compared after the tag prefix is stripped.
- Shape pins in `tests/test_promote_release.py`, behaviour tests in `tests/test_promote_latest_guard.py`; `docs/RELEASE_CYCLE.md` hotfix runbook rule points at the guard, plus a troubleshooting entry.

Entry is in the Unreleased changelog section; consumers pick it up with the next devkit release via `devkit-upgrade`.

