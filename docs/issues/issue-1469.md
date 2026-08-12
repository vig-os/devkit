---
type: issue
state: closed
created: 2026-08-12T12:02:33Z
updated: 2026-08-12T12:26:23Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1469
comments: 2
labels: chore, docs, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:34.504Z
---

# [Issue 1469]: [[CHORE] doctor comments still claim worktree-start unsets core.hooksPath on purpose](https://github.com/vig-os/devkit/issues/1469)

### Description

After #1463 (PR #1464), `just worktree-start` no longer unsets `core.hooksPath` — when the setting exists it is left untouched and the tracked `.githooks` shims cover the new worktree; the `prek install` path survives only as a fallback for repos with no hooks path configured.

The `doctor` recipe comments added by #1454 still describe the pre-fix behavior. In both `justfile` and the scaffolded `assets/workspace/justfile`, the linked-worktree branch is annotated along the lines of "`just worktree-start` unsets `core.hooksPath` in the worktree on purpose — prek refuses to install its shims while it is set — and installs those shims into the shared git dir instead."

The doctor *logic* is still correct: the shared-hooks PASS branch legitimately covers pre-fix worktrees and the fallback path, and a post-#1463 worktree simply hits the first branch (`PASS git hooks: core.hooksPath -> .githooks`). Only the comments are wrong.

### Why it matters

The #1430 → #1454 → #1461 → #1463 chain shows how much debugging in this area leans on these comments being truthful. A comment asserting that the repo-wide unset "is on purpose" would actively mislead the next investigation into hook state.

### Proposed Solution

Update the comments in both copies to describe the post-#1463 reality: the unset+install path is the *fallback* for repos without a configured hooks path, and the shared-`.git/hooks` PASS branch also covers worktrees created before #1463. Comment-only change, no behavior delta, no test or changelog impact.

Refs: #1454, #1463, #1464
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 12:08 PM_

Scope note: the same stale pre-#1463 claim also lives in test comments — tests/bats/doctor.bats, tests/bats/consumer-doctor.bats, tests/test_flake_hooks.py. Folding those into this issue's PR (same stale statement, comment-only, one traceable unit) rather than filing a separate issue.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 12, 2026 at 12:26 PM_

Fixed by PR #1471, squash-merged into release/1.8.0 (release-branch merges don't auto-close). Doctor comments in both justfile copies now describe the post-#1463 behavior, and the same stale claim was fixed in doctor.bats, consumer-doctor.bats, and test_flake_hooks.py per the scope note above. Ships in 1.8.0.

