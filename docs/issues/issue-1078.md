---
type: issue
state: closed
created: 2026-07-14T16:51:05Z
updated: 2026-07-14T21:02:09Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1078
comments: 1
labels: bug, priority:medium, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:32.698Z
---

# [Issue 1078]: [fix(ci): prepare-release rollback skipped on workflow cancellation](https://github.com/vig-os/devkit/issues/1078)

Found during review of release PR #1068.

After the `prepare` → `extension` → `open-pr` split, the `rollback` job's `if:` only fires on `result == 'failure'`. If the workflow is **cancelled** after the freeze commit lands (but before completion), rollback is skipped and the partial `release/X.Y.Z` branch plus the freeze commit on `dev` are left behind.

Not a regression (pre-split `if: failure()` behaved the same), but the split made the branching explicit and the cancel gap easy to close.

**Suggested:** extend the guard with `|| <job>.result == 'cancelled'`.

**File:** `.github/workflows/prepare-release.yml:414`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1089.

