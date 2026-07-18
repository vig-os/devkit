---
type: issue
state: closed
created: 2026-07-17T18:43:45Z
updated: 2026-07-17T19:39:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1195
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:23.111Z
---

# [Issue 1195]: [init-workspace.sh chmod +x sweeps pre-existing consumer .sh files it does not own](https://github.com/vig-os/devkit/issues/1195)

## Description

Found during the exo-fleet deploy (exo-pet/exo-fleet#230), reproduced on both the rc3 and rc4 re-scaffold: `init-workspace.sh --force` set the executable bit on **five pre-existing consumer `.sh` files that are sourced libraries, not executables** (they had no +x by design). The agent had to `chmod -x` / revert them before committing each time.

## Root cause (to confirm)

The scaffold applies `chmod +x` too broadly — presumably a blanket sweep over `*.sh` (or a whole tree) rather than only the scripts devkit itself delivers.

## Fix

Restrict the executable-bit application to the **scaffold-delivered** script set (the files init-workspace.sh actually copies from the template), never pre-existing consumer files. A repo's own sourced-only libs must keep their mode.

## Impact

Low — cosmetic mode churn a careful consumer reverts, but on a re-scaffold it silently re-dirties files every time and is easy to commit by accident.

Refs: exo-pet/exo-fleet#230.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 07:39 PM_

Fixed on `release/1.4.0` via merge 47167743 (PR #1199) (TDD: failing test + fix). Auto-close didn't fire because the PR targeted the release branch, not the default branch. Ships in 1.4.0.

