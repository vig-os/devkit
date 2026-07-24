---
type: issue
state: closed
created: 2026-07-21T07:48:58Z
updated: 2026-07-21T11:59:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1233
comments: 1
labels: chore, area:workspace
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:40.121Z
---

# [Issue 1233]: [Trunk render leaves sync-main-to-dev prose mentions in promote-release.yml](https://github.com/vig-os/devkit/issues/1233)

## Problem

Follow-up to #1226 (which scrubbed the ci.yml / codeql.yml / sync-issues.yml prose spots, PR #1229). Review of that PR found the same class of residue in a file `render_workflow_model()` does not touch at all:

- `assets/workspace/.github/workflows/promote-release.yml:8` — "(triggers sync-main-to-dev)"
- `assets/workspace/.github/workflows/promote-release.yml:473` — "(sync-main-to-dev may run next)"

`sync-main-to-dev.yml` is **not** rendered in trunk mode (confirmed absent from trunk scaffolds), so trunk consumers ship two comments referencing a workflow that doesn't exist in their repo.

## Impact

Cosmetic only, same as #1226 — pre-existing gap, not a regression from PR #1229. Completes the "trunk scaffold has no lying dev-model prose" invariant.

## Suggested fix

Extend the trunk prose scrub in `render_workflow_model()` to promote-release.yml (or make the comments model-neutral), with negative test assertions in `tests/test_workflow_model.py` mirroring the #1226 pattern.

Refs: #1226, #1205
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:59 AM_

Fixed on dev via PR #1243 (merge commit 10527550): render_workflow_model now drops both sync-main-to-dev parentheticals from promote-release.yml in trunk mode; gitflow render proven byte-identical (file added to the byte-identical guard tuple). Ships with 1.4.1.

