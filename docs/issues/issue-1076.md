---
type: issue
state: open
created: 2026-07-14T16:51:03Z
updated: 2026-07-14T16:51:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1076
comments: 0
labels: refactor, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:21.774Z
---

# [Issue 1076]: [refactor(workspace): make strip_banner style argument required](https://github.com/vig-os/devkit/issues/1076)

Found during review of release PR #1068.

`strip_banner(text, style="html")` defaults `style` to `html`. That's correct for the current sole caller, but a future hash-style caller who forgets the kwarg would get wrong header splitting (no shebang / doc-start handling) and could corrupt a file.

**Suggested:** make `style` a required argument to remove the footgun.

**File:** `scripts/transforms.py:105`

