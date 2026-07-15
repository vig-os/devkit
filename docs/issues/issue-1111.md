---
type: issue
state: closed
created: 2026-07-15T10:04:19Z
updated: 2026-07-15T14:57:06Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1111
comments: 1
labels: bug, priority:low, area:workspace, effort:medium, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:03.632Z
---

# [Issue 1111]: [[BUG] #1092 seam: upgrade drops prior hand-added root ignores instead of migrating them into the empty-seeded .gitignore.project](https://github.com/vig-os/devkit/issues/1111)

## Summary

Follow-up from **1.2.1-rc1 verification** (not fixed in the 1.2.1 train). Relates to #1092 (durable committed home for repo-root ignores via `.gitignore.project`).

## Problem

The #1092 fix gives consumers a durable, preserved `.gitignore.project` whose contents `init-workspace.sh` appends to the regenerated root `.gitignore`. But on the upgrade that *introduces* `.gitignore.project`, it is seeded **empty**. Any root ignores a consumer had previously hand-added directly to the managed root `.gitignore` (which the upgrade regenerates from scratch) are silently dropped — they are not migrated into the newly-seeded `.gitignore.project`.

The flake-hooks store-symlink case for `.pre-commit-config.yaml` is handled separately (auto-seeded conditionally, #1092 Fixed). This is about the *general* class: `.DS_Store`, editor/OS cruft, project-specific paths, etc. that a consumer added by hand.

## Suggested fix

Either:
- Auto-migrate previously-present, consumer-added lines from the old root `.gitignore` into `.gitignore.project` on the upgrade that introduces it; or
- At minimum, print an upgrade-output note listing the root-`.gitignore` lines being dropped, so the consumer can move them into `.gitignore.project` themselves.

## SemVer

Patch — data-preservation fix.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:57 PM_

Fixed by #1129 (merged into `dev`). Consumer hand-added root `.gitignore` entries are now auto-migrated append-only into `.gitignore.project` before the render — deduplicated against managed sources and existing entries, idempotent across upgrades, with an upgrade note listing what moved. Ships with the next patch release.

