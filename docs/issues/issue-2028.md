---
type: issue
state: open
created: 2026-11-04T04:58:31Z
updated: 2026-11-04T04:58:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2028
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:29.252Z
---

# [Issue 2028]: [prepare-release: dev CHANGELOG commit can revert concurrent entries (no BASE_SHA)](https://github.com/vig-os/devkit/issues/2028)

Found in the review of #2024 (#2003). prepare-release's freeze commit to dev goes through vig-os/commit-action without `BASE_SHA`. The action builds on dev's current head and replaces CHANGELOG.md (and the mirror) with content computed from an earlier checkout. Any changelog entry merged into dev between checkout and commit is silently lost.

Fix: pass the checkout SHA as `BASE_SHA`, so a moved dev fails the update instead of overwriting it. Apply this to the devkit and consumer copies, and to any other commit-action call that writes files computed from an earlier checkout. Audit all callers.

Refs: #2003
