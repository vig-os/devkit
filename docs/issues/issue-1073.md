---
type: issue
state: open
created: 2026-07-14T16:50:59Z
updated: 2026-07-14T16:50:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1073
comments: 0
labels: bug, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:23.038Z
---

# [Issue 1073]: [fix(vigutils): prepare-changelog finalize fails on re-run with a changed --tag-prefix](https://github.com/vig-os/devkit/issues/1073)

Found during review of release PR #1068.

`prepare-changelog finalize` is designed to be re-runnable on a reused release branch. But if it runs a second time with a **different** `--tag-prefix` (e.g. first `""`, then `"v"`), it raises `ValueError`: the already-finalized heading doesn't match the finalized pattern for the new prefix, and it no longer matches the `TBD` pattern either.

Failing without corrupting is acceptable, but the docstring's "reuse branch" idempotency claim doesn't cover a changed prefix.

**Suggested:** either normalize/re-finalize across a prefix change, or emit a clearer error naming the mismatch, and update the docstring to state the invariant (prefix must be stable across re-runs).

**File:** `packages/vig-utils/src/vig_utils/prepare_changelog.py:461`

