---
type: issue
state: open
created: 2026-07-14T16:51:07Z
updated: 2026-07-14T16:51:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1079
comments: 0
labels: refactor, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:20.611Z
---

# [Issue 1079]: [refactor(ci): drop full setup-env from prepare-release open-pr job](https://github.com/vig-os/devkit/issues/1079)

Found during review of release PR #1068.

The `open-pr` job runs the full `setup-env` composite (nix + `uv sync`) purely to invoke `gh pr create`. That adds a few minutes to the release critical path for no benefit — a bare checkout would suffice.

**Suggested:** drop `setup-env` from `open-pr` and use a minimal checkout.

**File:** `.github/workflows/prepare-release.yml:310`

