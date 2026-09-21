---
type: issue
state: closed
created: 2026-09-18T13:25:57Z
updated: 2026-09-21T06:53:42Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1651
comments: 1
labels: feature, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-21T07:52:32.537Z
---

# [Issue 1651]: [Scaffold ships Apache-2.0 LICENSE + a CHANGELOG that re-appear on every upgrade — no opt-out for private/release-less consumers](https://github.com/vig-os/devkit/issues/1651)

## Problem

`install.sh --force` unconditionally **adds** two files to a consumer that lacks them:

- `LICENSE` — the **Apache-2.0** template. For a private, proprietary consumer repo this is actively wrong: it mislabels confidential material as openly licensed, and there is no way to ship a proprietary/all-rights-reserved notice instead.
- `CHANGELOG.md` — the Keep-a-Changelog skeleton (which currently even carries a templated `## Unreleased` entry referencing an upstream issue). A consumer with `DEVKIT_FEATURES_DISABLED=release` cuts no releases and has no use for it.

Because both are `add-if-absent`, deleting them is not durable — the next `install.sh --force` re-adds them. A relaxed/private consumer must re-delete on every upgrade.

## Impact

Any private or release-less consumer (e.g. a docs/lab-notebook repo on `DEVKIT_WORKFLOW=trunk` + `DEVKIT_FEATURES_DISABLED=release,renovate,…`) has to carry an inappropriate license and an unused changelog, or fight the scaffold each upgrade.

## Proposed options (any one)

1. **`DEVKIT_LICENSE` knob** — `apache-2.0` (default, unchanged) | `proprietary` (ships an all-rights-reserved/confidential notice) | `none` (don't manage LICENSE). Mirrors how other `.vig-os` knobs gate scaffold shape.
2. **Gate `CHANGELOG.md` on the `release` feature group** — if `release` is in `DEVKIT_FEATURES_DISABLED`, don't scaffold or re-add `CHANGELOG.md` (and prune a prior copy, like the other feature-disabled paths).
3. At minimum, make both **preserve-if-consumer-deleted** (respect an intentional absence recorded in `.vig-os`, e.g. via `DEVKIT_UPGRADE_EXCLUDE`-style suppression) so a one-time removal sticks.

Context: surfaced upgrading a private consumer from 1.3.1 → 1.15.1; both files had to be removed post-upgrade and will re-appear on the next forced scaffold.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 21, 2026 at 06:53 AM_

Solved on `dev` in #1655 (merge commit 452f3842): the root `CHANGELOG.md` now follows the `release` feature group, and `DEVKIT_LICENSE` (`apache-2.0` | `proprietary` | `none`) governs the license. Both deletions are durable; neither value ever deletes an existing file. Closing manually — `Closes #` only fires on a main-branch merge.

Follow-up split out: #1656 (release-disabled consumers keep release-only `just` recipes referencing a changelog).

