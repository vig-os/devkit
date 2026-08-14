---
type: issue
state: closed
created: 2026-08-14T09:13:28Z
updated: 2026-08-14T12:40:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1511
comments: 1
labels: feature, priority:medium, area:ci, effort:small, semver:minor
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:13.281Z
---

# [Issue 1511]: [[FEATURE] Consumer abandon-release: ship the workflow the scaffold recipe would dispatch](https://github.com/vig-os/devkit/issues/1511)

### Description

#1504 added `just abandon-release X.Y.Z` + `abandon-release.yml` to devkit as the first-class rejection path at promote time. The recipe is kept **devkit-only** by a `RemoveBlock` transform in `scripts/manifest.toml` (the `justfile.gh` sync), because the consumer scaffold does not yet ship the workflow the recipe dispatches — a synced recipe would dispatch a nonexistent workflow.

**Proposed change:** ship the consumer variant.

- Add `assets/workspace/.github/workflows/abandon-release.yml`. Devkit's copy is already generic (draft Release by id, tag, PR, branch — no GHCR/devkit-specific steps) and the scaffold's `promote-release.yml` already uses the same `RELEASE_APP_CLIENT_ID`/`RELEASE_APP_PRIVATE_KEY` secrets, so this is close to a verbatim copy; adapt the tag name for `DEVKIT_TAG_PREFIX` (consumers may tag `vX.Y.Z`).
- Drop the `RemoveBlock` from `scripts/manifest.toml` so the recipe syncs into `assets/workspace/.devcontainer/justfile.gh`.
- Extend `tests/test_integration.py`'s scaffold recipe-list test and add a both-copies shape test for the workflow.
- Document in `docs/DOWNSTREAM_RELEASE.md`.

### Invariants / Constraints

- Draft-only precondition enforced server-side, identical to devkit's (published release ⇒ hard refusal; tombstone protection).
- Tag deletion only when no GitHub Release remains attached.

### Changelog Category

Added

### Additional Context

Split out of #1504 (see the `RemoveBlock` comment in `scripts/manifest.toml`). Related: #1506 (protection-aware promote gates, same solo-consumer class).
---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 12:40 PM_

Delivered by #1512 (merged to dev): the scaffold ships abandon-release.yml (draft-only guards, DEVKIT_TAG_PREFIX-composed tag via resolve-toolchain, publish-release lane), the recipe syncs into the consumer justfile.gh, and the workflow is registered in the release feature group, zizmor baseline, and renovate managed-file exclusion. Documented in docs/DOWNSTREAM_RELEASE.md.

