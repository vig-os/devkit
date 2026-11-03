---
type: issue
state: open
created: 2026-10-13T01:46:06Z
updated: 2026-10-13T01:46:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1879
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:39.203Z
---

# [Issue 1879]: [scaffold ships .claude/worktrees.json and agent-models.toml even with worktree,skills disabled; worktrees.json runs uv sync on non-Python repos](https://github.com/vig-os/devkit/issues/1879)

## What happens
gerchowl/nodd adopted devkit 1.19.0-rc1 (direnv, gitflow) with `DEVKIT_FEATURES_DISABLED=scanning,skills,worktree,gh-templates`. The scaffold still committed `.claude/worktrees.json` and `.claude/agent-models.toml`. `worktrees.json` runs `uv sync`, which fails in a Rust-only repo (there's no pyproject.toml).

## Expected
- Files that belong to a disabled feature group (`worktree`, `skills`) aren't scaffolded.
- A language-specific setup step (`uv sync`) is guarded by the repo's declared languages, as justfile.project recipes are since #1478.

Found by an independent review of the nodd adoption PR.
