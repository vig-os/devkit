---
type: issue
state: closed
created: 2026-08-12T09:44:54Z
updated: 2026-08-12T11:04:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1454
comments: 1
labels: bug, priority:medium, area:workflow, effort:small, semver:patch
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:38.904Z
---

# [Issue 1454]: [[BUG] just doctor reports git hooks inert inside linked worktrees, where they are live](https://github.com/vig-os/devkit/issues/1454)

### Description

`just doctor` reports `WARN git hooks: ... tracked but inert` inside a linked worktree created by `just worktree-start`, **even though the hooks are live there**. The diagnostic lies, in the direction that matters.

`justfile.worktree` deliberately unsets the setting (`justfile.worktree:202`, and the scaffolded copy at `assets/workspace/.devcontainer/justfile.worktree:205`):

```sh
git config --unset-all core.hooksPath 2>/dev/null || true
```

and installs prek hooks into `.git/hooks` instead. `mkProjectShell`'s `githooksPathHook` (#1112) likewise guards itself to the main worktree, so it does not re-set it. An unset `core.hooksPath` in a linked worktree is therefore the **correct, intended** state — but both `doctor` recipes read it as the fresh-clone failure case.

Affects **both** copies:

- devkit's own `justfile` (`doctor`, the `core.hooksPath` block added in #1430)
- the scaffolded `assets/workspace/justfile` (`doctor`, added in #1448)

### Steps to Reproduce

```
just worktree-start <issue>       # or: git worktree add ../wt-x -b feature/x-y
cd ../<worktree>
just doctor
```

### Expected Behavior

A verdict that reflects reality: in a linked worktree with prek hooks installed at `.git/hooks`, report `PASS` (with wording that makes the worktree case explicit), not the fresh-clone `WARN`.

### Actual Behavior

`WARN git hooks: core.hooksPath not set, .githooks is tracked but inert (run: ...)` — and the remediation it suggests would actively **undo** the worktree setup.

### Proposed Solution

Detect the linked-worktree case (git-dir != common-dir, e.g. `test "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)"`) and, when an installed hook is present at `.git/hooks/pre-commit`, report `PASS` with worktree-specific wording. Keep the existing fresh-clone `WARN` for every other unset case, including a linked worktree with **no** installed hook — that one is genuinely inert and must stay a `WARN`.

### Additional Context

Not a regression — both recipes have behaved this way since their respective diagnostics landed. But a diagnostic that reports "inert" when the gates are live is exactly the failure class #1430 exists to close, and it will be hit constantly: the `worktree_*` autonomous pipelines are a primary devkit workflow.

**Fix both recipes in the same change.** #1448 added a drift-guard test (`consumer doctor checks exactly what devkit's doctor checks`) that asserts the two recipes' check-label sets are identical, so they must stay in step. Surfaced as a known limitation in #1448.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 11:04 AM_

Fixed by #1461, merged to `release/1.8.0` as 4c6d57dc (post-recovery base 9cce85ed).

Both `doctor` recipes — devkit's `justfile` and the scaffolded `assets/workspace/justfile` — now report a linked worktree with an installed, executable `hooks/pre-commit` as `PASS git hooks: linked worktree, installed at <path> (core.hooksPath unset by design)`. A linked worktree with **no** installed shim is genuinely inert and still WARNs, as do all other unset and set-elsewhere cases.

**Two mechanics the obvious implementation gets wrong**, both established empirically:

- `.git` is a **file** in a linked worktree, so the literal `.git/hooks/pre-commit` test suggested in this issue can never see the shim. The fix uses `git rev-parse --git-path hooks/pre-commit` — the file git itself would run.
- `--absolute-git-dir` vs `--path-format=absolute --git-common-dir` is the safe comparison; a plain `--git-dir`/`--git-common-dir` compare falsely reports "linked" from a *subdirectory* of the main worktree. Same idiom `githooksPathHook` already uses.

**Grounded in behavior, not inference:** in a live linked worktree `git commit -m "bad message"` was rejected by `validate-commit-msg`; after deleting the shims the same commit landed unblocked — confirming the retained WARN is true in that state.

Evidence: RED showed exactly 2 failures (`not ok 6`, `not ok 23`) both displaying the lying WARN, with the other 4 new tests green as intended; full bats **502 ok / 0 not ok**; `prek run --all-files` exit 0; full pytest 776 passed / 20 skipped / 1 failed (the known stale-image test, verified pre-existing two ways). #1448's drift guard still passes — the new PASS keeps the `git hooks` label so both recipes' label sets stay identical — and `refute_output --partial "scripts/init.sh"` was added to both new consumer tests.

Merged only after confirming zero `release.yml` runs in flight (see #1462).

**Left unchanged deliberately:** main worktree + unset `core.hooksPath` + a prek shim in `.git/hooks` still WARNs. Literally true and its remediation is harmless, and this issue explicitly says to keep the fresh-clone WARN for every other unset case. Worth a follow-up if `doctor` should key purely off "what will git execute".

**Separate bug found and filed as #1463:** `just worktree-start` unsets `core.hooksPath` in the **shared** config, so creating a worktree disarms the **main** checkout's hooks. `doctor` now correctly WARNs about that state.

