---
type: issue
state: open
created: 2026-10-09T14:25:42Z
updated: 2026-10-13T02:13:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1854
comments: 1
labels: bug, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:43.578Z
---

# [Issue 1854]: [direnv mode: outside the dev shell, commits skip every hook silently and `just precommit` fails with 'No prek.toml or .pre-commit-config.yaml found'](https://github.com/vig-os/devkit/issues/1854)

Seen in vig-os/vigil (devkit 1.18.0, `DEVKIT_MODE=direnv`, Rust pack) on 2026-10-09, with agents working in fresh `git worktree`s.

- `git config core.hooksPath` is **unset** in the checkout, and there's no `.pre-commit-config.yaml` (the hook config is flake-generated). A `git commit` from a plain shell (no `nix develop` / direnv not loaded, which is the default in a new linked worktree until `direnv allow`) runs **no hooks at all**, silently. The `.githooks/*` shims would refuse with "Please commit your changes within the dev container or the nix dev-shell", but they aren't wired, so they never run.
- `just precommit` outside the shell fails with: `No \`prek.toml\` or \`.pre-commit-config.yaml\` found in the current directory or parent directories`.

Two of three agents hit this in one session and committed unhooked. CI's commit-checks lane re-validates messages, but not the other pre-commit hooks.

**Suggestions:** make the failure loud and actionable: `just precommit` re-execs via `nix develop -c` (or prints "run inside `nix develop`"), and set `core.hooksPath=.githooks` at scaffold or `just init` time so the shim's sanctioned-environment guard actually fires outside the shell. Also consider documenting `direnv allow` for new worktrees in the worktree skills.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 13, 2026 at 02:13 AM_

Related case from a downstream consumer (gerchowl/cue, devkit 1.18.0, direnv mode, gitflow): in **linked worktrees** (agent delegates each work in one), `core.hooksPath` is unset because the dev-shell entry only sets it in the main worktree (COMMIT_MESSAGE_STANDARD.md:107 "guarded to the main worktree"). Commits there silently skip commit-msg and pre-commit; a reviewer confirmed with `git config core.hooksPath` empty in the worktree and an invalid message accepted. Workaround in use: `git config core.hooksPath .githooks` per worktree (relative, resolves per worktree) or `git -c core.hooksPath=.githooks commit`. Suggest: set it per worktree via `git config --worktree` (with `extensions.worktreeConfig`) on shell entry, or have `just doctor` fail loudly in a worktree with no hooksPath.

