---
type: issue
state: closed
created: 2026-08-12T10:55:29Z
updated: 2026-08-12T11:40:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1463
comments: 1
labels: bug, priority:medium, area:workflow, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:35.366Z
---

# [Issue 1463]: [[BUG] just worktree-start unsets core.hooksPath repo-wide, disarming the main checkout's hooks](https://github.com/vig-os/devkit/issues/1463)

### Description

`just worktree-start` runs `git config --unset-all core.hooksPath` from inside the new linked worktree. `core.hooksPath` is **shared** repo config, not per-worktree — so the unset applies to the whole repository, leaving the **main checkout's** `.githooks` inert until something re-sets it.

`justfile.worktree:202` (and the scaffolded copy at `assets/workspace/.devcontainer/justfile.worktree:205`):

```sh
git config --unset-all core.hooksPath 2>/dev/null || true
```

The unset is correct *for the worktree* — prek refuses to install its shims while `core.hooksPath` is set, and the worktree gets its own shims in the common git dir instead. The bug is that it is not scoped, so it silently disarms the main worktree's commit-side gates.

### Steps to Reproduce

```
git config core.hooksPath            # .githooks
just worktree-start <issue>
cd <main worktree>
git config core.hooksPath            # exits 1 — unset
```

Reproduced during #1454.

### Expected Behavior

Creating a worktree must not change how the main checkout enforces hooks. The main worktree keeps `core.hooksPath=.githooks` and keeps running the tracked shims.

### Actual Behavior

`core.hooksPath` is cleared repo-wide. The main worktree then runs whatever is in `.git/hooks` — which is prek's shims if a worktree installed them, and nothing at all otherwise. In the latter case every commit-side gate on the main checkout is silently inert: exactly the #1430 failure mode, self-inflicted.

### Proposed Solution

Not prescriptive. `--worktree`-scoped config (`git config --worktree --unset-all core.hooksPath`) is the obvious candidate, but it requires `extensions.worktreeConfig` to be enabled, so the change needs care and its own test. Alternatives include restoring the setting on `worktree-stop`/`worktree-clean`, or having the worktree flow avoid unsetting at all if prek can be pointed elsewhere.

Whatever the fix, it should cover **both** copies (devkit's `justfile.worktree` and the scaffolded one) and be pinned by a bats test that asserts the main worktree's `core.hooksPath` survives a `worktree-start`.

### Impact

Anyone using the `worktree_*` autonomous pipelines — a primary devkit workflow — silently loses local commit-side enforcement on their main checkout. It is invisible until a bad commit gets through.

Mitigation already in place: after #1454, `just doctor` correctly reports the main worktree as `WARN git hooks: … tracked but inert` in this state, so the condition is now at least detectable.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 11:40 AM_

Fixed by PR #1464, squash-merged into release/1.8.0 @1dcd0ea6 (release-branch merges don't auto-close). worktree-start now leaves a configured core.hooksPath untouched and skips the prek install — the tracked .githooks shims cover the new worktree; the prek-install path remains as the fallback when no hooks path is set. Both justfile.worktree copies fixed, pinned by bats tests driving the real recipe in a sandbox. Ships in 1.8.0.

