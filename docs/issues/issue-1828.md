---
type: issue
state: open
created: 2026-10-05T18:35:58Z
updated: 2026-10-13T02:48:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1828
comments: 1
labels: bug, priority:medium, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:44.618Z
---

# [Issue 1828]: [Dev-shell-only hooks break git rebase halfway, with no recovery hint](https://github.com/vig-os/devkit/issues/1828)

## Problem
The scaffolded `.githooks/*` refuse to run outside the dev shell ("Please commit your changes within the dev container or the nix dev-shell."). That includes `prepare-commit-msg` during `git rebase`. A rebase started from a plain shell stops halfway, and the recovery path is non-obvious.

## Repro
1. From a plain shell, outside `nix develop`/direnv: `git rebase <base>`.
2. The first pick fails with `error: 'prepare-commit-msg' hook failed`. The pick is left **staged** and rescheduled.
3. `git rebase --continue` inside the dev shell then fails with `error: you have staged changes in your working tree`.
4. Recovery is `git commit -C <original-sha> && git rebase --continue`, which nothing prints.

## Proposed
- Let `prepare-commit-msg` and `commit-msg` pass through during history replays (rebase, cherry-pick, `--amend` without a message change). Detect these via `GIT_REFLOG_ACTION` (`rebase*`, `cherry-pick`) or the presence of `.git/rebase-merge`/`rebase-apply`. They only strip or validate messages that were already validated when first committed.
- Failing that, print the recovery steps in the refusal message when a rebase is in progress.

---

# [Comment #1]() by [gerchowl]()

_Posted on October 13, 2026 at 02:48 AM_

Downstream confirmation (gerchowl/cue, devkit 1.18.0, direnv mode, gitflow): three independent agent sessions hit this rebasing PR branches onto `dev` in linked worktrees. (1) Outside the dev shell: `error: 'prepare-commit-msg' hook failed`, replay stops with changes staged and no conflict markers; (2) inside `nix develop`, `git rebase --continue` then refuses with `error: you have staged changes in your working tree`; committing by hand (`git commit -C <sha>`) makes the next replay report `could not apply <sha>` (AA conflict), recoverable only with `git rebase --skip`; (3) one session bypassed with `git -c core.hooksPath=/dev/null rebase` and re-ran all hooks at the final head. Expected: hooks that require the dev shell should no-op (or re-enter the shell) during `GIT_REFLOG_ACTION=rebase*` replays, or print the recovery recipe.

