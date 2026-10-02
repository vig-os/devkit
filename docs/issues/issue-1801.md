---
type: issue
state: closed
created: 2026-10-01T14:09:12Z
updated: 2026-10-01T17:46:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1801
comments: 1
labels: bug, priority:high
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:22.035Z
---

# [Issue 1801]: [fix: fresh scaffold commit fails check-added-large-files on .devcontainer/CHANGELOG.md](https://github.com/vig-os/devkit/issues/1801)

### Description

A new devcontainer/both-mode consumer's first scaffold commit fails `check-added-large-files`: the scaffold copies devkit's `CHANGELOG.md` to `.devcontainer/CHANGELOG.md`, and that file is now over the hook's 500 KB default (514,976 bytes at 1.17.0; 528,063 on `dev`). Found while building the #1762 consumer matrix.

### Steps to Reproduce

1. Render a fresh workspace with `init-workspace.sh --no-prompts --mode both`.
2. `git init && git add -A`, then `prek run` (staged files, as a first `git commit` does).

### Expected Behavior

A fresh scaffold commits cleanly with its own hooks.

### Actual Behavior

`check-added-large-files` rejects `.devcontainer/CHANGELOG.md` (> 500 KB).

### Environment

devkit 1.17.0 (the file crossed 500 KB with the 1.17.0 changelog); grows every release.

### Additional Context

Existing consumers are unaffected (the hook checks only *added* files; upgrades modify it). Devkit's own root `CHANGELOG.md` is likewise only ever modified.

### Possible Solution

Exclude `^\.devcontainer/CHANGELOG\.md$` from `check-added-large-files` in the scaffold hook definition (nix/hooks.nix is the SSoT for the rendered config). A preserved consumer config does not need a fold: the file is already added there.

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 05:46 PM_

Fixed by #1805 (merged to `dev`, ships with the next release): `check-added-large-files` excludes `^\.devcontainer/CHANGELOG\.md$`. Existing consumers need nothing, since the hook only checks added files.

