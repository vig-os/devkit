---
type: issue
state: open
created: 2026-07-14T16:51:02Z
updated: 2026-07-14T16:51:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1075
comments: 0
labels: docs, priority:backlog, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:22.259Z
---

# [Issue 1075]: [docs(vigutils): note x1f/x1e separator assumption in validate-commit-range](https://github.com/vig-os/devkit/issues/1075)

Found during review of release PR #1068.

The comment justifies using non-newline field separators (bodies can contain newlines) but doesn't note that a commit body containing raw `\x1f` / `\x1e` bytes would silently misparse — git does not escape either. Not a real-world failure mode, but the comment should acknowledge the assumption.

Comment-only clarification.

**File:** `packages/vig-utils/src/vig_utils/validate_commit_range.py:44`

