---
type: issue
state: open
created: 2026-10-05T18:35:59Z
updated: 2026-10-05T18:35:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1829
comments: 0
labels: feature, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:50:58.607Z
---

# [Issue 1829]: [direnv mode: commits before the first dev-shell entry run unhooked; let install.sh set core.hooksPath](https://github.com/vig-os/devkit/issues/1829)

## Problem
Follow-up to #1112. In direnv mode, `core.hooksPath` is set on the first dev-shell entry. Any commit made between `install.sh` and the first `direnv allow`/`nix develop` runs with no hooks at all, and nothing says so. In practice that is the initial scaffold commit, plus any quick commit right after it.

## Proposed
Have `install.sh` set `git config core.hooksPath .githooks` itself in direnv (and both) mode. It is local config, idempotent and free, and the shell-entry hook stays as the self-heal for fresh clones. At minimum, print in the install summary that hooks are inactive until the first shell entry.

