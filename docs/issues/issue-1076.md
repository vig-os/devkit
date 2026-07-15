---
type: issue
state: closed
created: 2026-07-14T16:51:03Z
updated: 2026-07-14T21:02:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1076
comments: 1
labels: refactor, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:33.246Z
---

# [Issue 1076]: [refactor(workspace): make strip_banner style argument required](https://github.com/vig-os/devkit/issues/1076)

Found during review of release PR #1068.

`strip_banner(text, style="html")` defaults `style` to `html`. That's correct for the current sole caller, but a future hash-style caller who forgets the kwarg would get wrong header splitting (no shebang / doc-start handling) and could corrupt a file.

**Suggested:** make `style` a required argument to remove the footgun.

**File:** `scripts/transforms.py:105`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1083.

