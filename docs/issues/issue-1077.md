---
type: issue
state: closed
created: 2026-07-14T16:51:04Z
updated: 2026-07-14T21:02:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1077
comments: 1
labels: docs, priority:backlog, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:33.002Z
---

# [Issue 1077]: [docs(workspace): document Banner.apply dropping leading blank lines](https://github.com/vig-os/devkit/issues/1077)

Found during review of release PR #1068.

`Banner.apply` silently drops leading blank lines in a source file (the "skip leading blanks in rest" loop). This is a one-shot normalization, not an ongoing drift, but it can surprise when diffing initial sync output.

**Suggested:** document the normalization in the function, or preserve leading blanks.

**File:** `scripts/sync_manifest.py:180`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1084.

