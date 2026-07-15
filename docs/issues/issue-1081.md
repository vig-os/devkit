---
type: issue
state: closed
created: 2026-07-14T16:51:09Z
updated: 2026-07-14T21:02:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1081
comments: 1
labels: docs, priority:backlog, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:31.810Z
---

# [Issue 1081]: [docs(ci): comment why sync-main-to-dev checkout drops ref: dev](https://github.com/vig-os/devkit/issues/1081)

Found during review of release PR #1068.

Dropping `ref: dev` from the checkout is safe because every subsequent op targets `origin/main` / `origin/dev` explicitly. But the intent is non-obvious — the checkout now exists only so the `.github/actions/setup-env` composite can be resolved.

**Suggested:** add a one-line comment stating the checkout is only for the composite-action lookup.

**File:** `.github/workflows/sync-main-to-dev.yml:110`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1085.

