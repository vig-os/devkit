---
type: issue
state: open
created: 2026-07-14T16:51:09Z
updated: 2026-07-14T16:51:09Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1081
comments: 0
labels: docs, priority:backlog, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:19.868Z
---

# [Issue 1081]: [docs(ci): comment why sync-main-to-dev checkout drops ref: dev](https://github.com/vig-os/devkit/issues/1081)

Found during review of release PR #1068.

Dropping `ref: dev` from the checkout is safe because every subsequent op targets `origin/main` / `origin/dev` explicitly. But the intent is non-obvious — the checkout now exists only so the `.github/actions/setup-env` composite can be resolved.

**Suggested:** add a one-line comment stating the checkout is only for the composite-action lookup.

**File:** `.github/workflows/sync-main-to-dev.yml:110`

