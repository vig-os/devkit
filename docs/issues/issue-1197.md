---
type: issue
state: closed
created: 2026-07-17T18:44:02Z
updated: 2026-07-17T19:39:06Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1197
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:22.476Z
---

# [Issue 1197]: [print_preserved_template_diff emits 'not a git repository' noise when scaffolding a worktree via bare podman](https://github.com/vig-os/devkit/issues/1197)

## Description

Found during the vault deploy (exo-pet/vault#31). When `init-workspace.sh` runs via bare `podman run -v <worktree>:/workspace` and `<worktree>` is a **git worktree** (not a primary checkout), `print_preserved_template_diff` printed `fatal: not a git repository: (null)` once per preserved file, and the template-divergence diffs for preserved files were silently suppressed.

## Root cause

A worktree's `.git` is a **file** (`gitdir: /path/outside/the/mount`) pointing at the main repo's `.git/worktrees/<name>`, which is **outside the bind mount**. Inside the container, `git` can't resolve it, so `git diff --no-index` (or whatever `print_preserved_template_diff` uses to show preserved-file divergence) fails to init a repo. The failure is swallowed (`|| true`) so the scaffold completes correctly, but the operator loses the preserved-file diff output.

## Fix options

- Detect the worktree/non-resolvable-git case and either (a) run the preserved-file diff with `git --no-index` in a way that doesn't require a repo (it shouldn't — `git diff --no-index a b` works outside a repo, so the failure may be an env/`GIT_DIR` leak worth investigating), or (b) fall back to a plain `diff` when git is unavailable, or (c) suppress the per-file `fatal:` line and print one clear 'diffs unavailable (worktree not resolvable in container)' notice.

## Impact

Low — non-fatal, scaffold output is correct; only the preserved-file divergence preview is lost and the log gains noise. Affects worktree-based bare-podman scaffolds (how the rollout agents run).

Refs: exo-pet/vault#31.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 07:39 PM_

Fixed on `release/1.4.0` via merge 480b0cc5 (PR #1202) (TDD: failing test + fix). Auto-close didn't fire because the PR targeted the release branch, not the default branch. Ships in 1.4.0.

