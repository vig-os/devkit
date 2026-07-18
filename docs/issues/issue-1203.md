---
type: issue
state: open
created: 2026-07-17T20:20:04Z
updated: 2026-07-17T20:20:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1203
comments: 0
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:21.944Z
---

# [Issue 1203]: [just emits 'fatal: not a git repository' on every invocation in a foreign-git worktree cwd (_wt_repo backtick)](https://github.com/vig-os/devkit/issues/1203)

## Description

Split out from #1197 (agent observation). Separate code path from `print_preserved_template_diff`.

`justfile.worktree` declares a top-level backtick variable:

```just
_wt_repo := `basename "$(git rev-parse --show-toplevel)"`
```

`just` evaluates top-level variable assignments **eagerly on every invocation** (not lazily per-recipe), so `git rev-parse --show-toplevel` runs for *any* `just <recipe>` — e.g. `just sync`, `just lint` — regardless of whether a worktree recipe is used. When the working directory is a git **worktree whose `.git` file points at a gitdir outside the (bind-mounted) tree** — exactly the bare-`podman` scaffold context from #1197 — `git rev-parse` fails and prints:

```
fatal: not a git repository: (null)
```

to stderr on every `just` call, and `_wt_repo` silently becomes `basename ""` = empty.

## Reproduce

```bash
d=$(mktemp -d); printf 'gitdir: /nonexistent/outside\n' > "$d/.git"
just -d "$d" -f justfile.worktree --evaluate _wt_repo   # -> fatal: not a git repository: (null)
```

## Root cause

The backtick command has no failure tolerance. Every `just` invocation in a cwd where git can't resolve a repo surfaces the raw `fatal:` line.

## Fix

Make the substitution tolerant, matching the idiom already used in `packages/vig-utils/src/vig_utils/shell/setup-labels.sh`:

```just
_wt_repo := `basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"`
```

The `_wt_repo`/`_wt_base` values only matter to the `worktree-*` recipes (never run in a broken-git context), so the `pwd` fallback is harmless there while removing the per-invocation noise everywhere else.

**SSoT:** fix the repo-root `justfile.worktree`; the scaffolded `.devcontainer/justfile.worktree` is regenerated from it via `scripts/manifest.toml` (src → dest), so the consumer copy inherits the fix on sync.

## Impact

Low — cosmetic log noise (no functional effect; the worktree recipes aren't used in that context). Affects every `just` call inside a foreign-git worktree cwd, e.g. rollout agents scaffolding via bare `podman run -v <worktree>:/workspace`.

Refs: #1197.
