---
type: issue
state: open
created: 2026-02-24T13:19:01Z
updated: 2026-06-23T06:56:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/178
comments: 1
labels: feature, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:56.227Z
---

# [Issue 178]: [Add [IDLE] status to worktree-list and idle mode to worktree-clean](https://github.com/vig-os/devcontainer/issues/178)

## Problem

`just wt-list` only shows `[RUNNING]` or `[STOPPED]`. When an agent finishes its task but the tmux session remains open (waiting for a new prompt), there's no way to distinguish an actively working agent from an idle one.

`just wt-clean` only supports cleaning stopped worktrees or all worktrees — no way to also clean idle ones while preserving actively running agents.

## Solution

### worktree-list
- Check `#{window_activity}` tmux variable to detect when a session's last output was > N minutes ago (default: 5 min, configurable via `WT_IDLE_MINUTES`)
- Show `[IDLE]` status for sessions with no recent activity

### worktree-clean
- Default (no args): clean stopped worktrees only (unchanged)
- `idle`: clean stopped + idle worktrees
- `all`: clean everything including running (unchanged)

## Acceptance criteria
- [ ] `just wt-list` shows `[IDLE]` for sessions idle > threshold
- [ ] `just wt-clean` default still cleans only stopped
- [ ] `just wt-clean idle` cleans stopped + idle, skips running
- [ ] `just wt-clean all` cleans everything (unchanged)
- [ ] BATS tests cover new behavior
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Built on the worktree pipeline migrated in #625 (#626 paths, #627 CLI swap). Verify idle mode still works once the pipeline is driven by `claude`. Coordinate — not superseded.

