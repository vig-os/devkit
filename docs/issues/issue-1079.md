---
type: issue
state: closed
created: 2026-07-14T16:51:07Z
updated: 2026-07-14T21:02:11Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1079
comments: 1
labels: refactor, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:32.406Z
---

# [Issue 1079]: [refactor(ci): drop full setup-env from prepare-release open-pr job](https://github.com/vig-os/devkit/issues/1079)

Found during review of release PR #1068.

The `open-pr` job runs the full `setup-env` composite (nix + `uv sync`) purely to invoke `gh pr create`. That adds a few minutes to the release critical path for no benefit — a bare checkout would suffice.

**Suggested:** drop `setup-env` from `open-pr` and use a minimal checkout.

**File:** `.github/workflows/prepare-release.yml:310`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1090.

