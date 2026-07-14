---
type: issue
state: closed
created: 2026-07-14T11:21:19Z
updated: 2026-07-14T12:07:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1056
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, area:docs, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:26.304Z
---

# [Issue 1056]: [[BUG] Scaffolded files reference docs the scaffold does not ship (ci.yml ADR link, DOWNSTREAM_RELEASE.md cross-links)](https://github.com/vig-os/devkit/issues/1056)

## Problem

Two more instances of the #1046 dangling-reference class, found while shipping #1051:

1. `assets/workspace/.github/workflows/ci.yml:4` references `docs/rfcs/ADR-conditional-container-toolchain.md`, which the scaffold does not ship — every consumer carries a dead pointer in its CI workflow header.
2. The newly scaffolded `docs/DOWNSTREAM_RELEASE.md` (#1046, synced verbatim from the root SSoT) cross-links devkit-internal docs a consumer repo does not have: `docs/RELEASE_CYCLE.md`, `docs/CROSS_REPO_RELEASE_GATE.md`, `docs/MIGRATION.md`, `docs/rfcs/ADR-conditional-container-toolchain.md`.

## Fix

Rewrite these references to absolute canonical URLs (`https://github.com/vig-os/devkit/blob/main/docs/...`). For `DOWNSTREAM_RELEASE.md` edit the root SSoT (absolute URLs work in both homes; the synced copy follows via sync-manifest). Companion lint: #1057 makes this class structurally detectable.

## Acceptance criteria

- [ ] No scaffolded file references a repo-relative path the scaffold does not ship (verified by the #1057 lint, or a targeted test if that issue lands later)
- [ ] Links resolve from both devkit and a consumer checkout

Refs: #1046, #1044

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:07 PM_

Fixed in #1063 (merged to dev): scaffold ci.yml ADR reference and all 8 DOWNSTREAM_RELEASE.md internal cross-links rewritten to absolute canonical URLs (root SSoT edited; synced copy follows). Remaining same-class refs tracked in #1062.

