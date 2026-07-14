---
type: issue
state: closed
created: 2026-07-14T11:21:20Z
updated: 2026-07-14T12:07:24Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1057
comments: 1
labels: feature, priority:medium, area:ci, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:25.912Z
---

# [Issue 1057]: [[FEATURE] Scaffold lint: unshipped-path references and non-default-ref local-action usage](https://github.com/vig-os/devkit/issues/1057)

## Problem

Three shipped bugs share two detectable shapes, each promised a lint in its postmortem:

- **Unshipped-path references** (#1046, and the instances in the companion fix issue): a scaffolded file points at a repo path the scaffold does not ship. "Scaffolded files must not reference repo paths the scaffold does not ship" — proposed in #1046.
- **Non-default-ref checkout + local action** (#1034): a workflow job that checks out a non-default ref must not `uses: ./...` — GitHub resolves local actions against the checked-out workspace, which caused the sync-main-to-dev bootstrap deadlock. Proposed in #1034.

## Proposed solution

A scaffold-lint test module (pytest, alongside the existing workflow-shape tests — `tests/test_workflow_sync_checkout.py` is the idiom) with one check per rule:

1. Walk `assets/workspace/` for repo-relative doc/path references (workflow header comments, markdown links) and assert each target exists within the scaffold tree. Allowlist absolute URLs; keep the reference-extraction conservative (few false positives beat exhaustive coverage).
2. Parse every scaffold + devkit workflow; for each job that checks out a ref other than the default branch, assert no step `uses: ./...`.

Both run as plain pytest in `Project Checks` — no new hook needed. The companion fix issue must land first (or in the same PR) so rule 1 starts green.

## Acceptance criteria

- [ ] Rule 1 fails on a scaffolded reference to an unshipped path (regression-tested by construction) and passes on the fixed tree
- [ ] Rule 2 fails on the pre-#1034 pattern and passes on the current tree
- [ ] Both cover devkit's own workflows where applicable

Refs: #1034, #1046
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 12:07 PM_

Implemented in #1063 (merged to dev): tests/test_scaffold_lint.py with both rules — unshipped-path references (empty allowlist, flagged exactly the known instances) and the #1034 non-default-ref/local-action class (pre-#1034 shape covered as a regression fixture). NOTE: runs in CI only once #1061 lands (the Project Checks pytest-scope fix, in flight).

