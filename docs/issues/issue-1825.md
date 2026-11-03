---
type: issue
state: open
created: 2026-10-05T18:35:53Z
updated: 2026-10-05T18:35:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1825
comments: 0
labels: bug, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:51:00.932Z
---

# [Issue 1825]: [First install into an empty clone: misleading 'existing files' and 'main not found' messages, no scaffold commit](https://github.com/vig-os/devkit/issues/1825)

## Problem
A first install into a freshly created, empty clone (unborn `main`, nothing but `.git`) prints two misleading messages and skips the scaffold commit:
```
Existing files detected; skipping the automatic scaffold commit.
Warning: Branch 'main' not found in existing repository
  The project workflow expects a 'main' branch.
```
No files existed before the scaffold, and `main` is not missing: it is unborn.

## Repro
```bash
gh repo create <owner>/<new> --public --clone && cd <new>
bash install.sh --mode direnv --workflow trunk .
```

## Expected
Treat "unborn default branch plus empty worktree" as a fresh repository: make the scaffold commit on `main`, and do not warn about a missing branch.

