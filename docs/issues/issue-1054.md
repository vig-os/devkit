---
type: issue
state: closed
created: 2026-07-14T11:20:47Z
updated: 2026-07-14T12:18:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1054
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:27.133Z
---

# [Issue 1054]: [[BUG] justfile.local header claims upgrade preservation, but the file is not in PRESERVE_FILES](https://github.com/vig-os/devkit/issues/1054)

## Problem

Found during #1036 / PR #1043: the scaffolded `justfile.local` (personal, gitignored recipes) ships a header claiming it is "preserved during upgrades", but it is **absent from `PRESERVE_FILES`** in `init-workspace.sh` — so a re-scaffold/upgrade actually overwrites it, silently destroying personal recipes. Same silent-clobber class as #878/#913. It was skip-listed from the banner pass precisely because giving it a *managed* banner would contradict its own text.

## Fix

Add `justfile.local` to `PRESERVE_FILES` (the header's claim is the correct intent for a personal, gitignored starter — align the mechanism with the promise, as #878/#913 did), remove it from `_BANNER_SKIP`, and let it receive the **preserved** banner variant derived from the now-correct classification.

## Acceptance criteria

- [ ] `justfile.local` is in `PRESERVE_FILES`; a re-scaffold over an existing file leaves it untouched (bats coverage, same idiom as justfile.project preservation tests)
- [ ] It carries the preserved banner variant; its old hand-written header no longer contradicts the mechanism

Refs: #1036, #878, #913
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:18 PM_

Fixed in #1064 (merged to dev): justfile.local is now in PRESERVE_FILES (upgrade-preservation bats-tested), carries the preserved banner, and its header no longer makes claims the mechanism doesn't back.

