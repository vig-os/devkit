---
type: issue
state: open
created: 2026-10-05T18:35:56Z
updated: 2026-10-05T18:35:56Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1827
comments: 0
labels: docs, priority:low, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:51:00.205Z
---

# [Issue 1827]: [SOLO_ADOPTION step 3 does not say the re-render must run off main](https://github.com/vig-os/devkit/issues/1827)

## Problem
`docs/SOLO_ADOPTION.md` step 3 says to apply the profile re-render "on a clean branch". In practice the preflight refuses on `main`:
```
warn: preflight: 'main' is a protected branch — upgrades need a dedicated branch.
```
On a brand-new solo repo, the profile is applied before any PR flow exists, and the doc gives no hint that `main` is excluded.

## Proposed
- Doc: say "a dedicated non-`main` branch". Show the commands: create a branch, re-render, commit, then fast-forward `main` (or open a PR).
- Optionally, allow the first profile application on `main` when the repo has no prior scaffold commit beyond the initial one.

