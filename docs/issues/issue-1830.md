---
type: issue
state: open
created: 2026-10-05T18:36:01Z
updated: 2026-10-05T18:36:01Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1830
comments: 0
labels: feature, priority:medium, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:50:57.781Z
---

# [Issue 1830]: [Refs validator rejects cross-repository references (owner/repo#N)](https://github.com/vig-os/devkit/issues/1830)

## Problem
`validate-commit-msg` (and CI's `validate-commit-range`) reject a cross-repository GitHub reference:
```
Refs: owner/repo#123
→ Refs line must contain at least one reference. Accepted: issue numbers (#36), REQ-..., RISK-..., SOP-...
```
Work driven by an issue in another repository (a design or spike issue tracked centrally, a consumer bug reported upstream) cannot be traced the standard way. Authors move the reference into the body, where nothing validates it, or drop it.

## Proposed
Accept GitHub's cross-repo form `[owner/]repo#N`, alongside `#N`, `REQ-`, `RISK-` and `SOP-`, in both the hook and the CI gate. Update `docs/COMMIT_MESSAGE_STANDARD.md` to match.

