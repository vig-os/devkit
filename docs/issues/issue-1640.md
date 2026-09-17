---
type: issue
state: closed
created: 2026-09-16T18:02:56Z
updated: 2026-09-17T07:10:48Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1640
comments: 1
labels: bug, area:workspace
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T07:29:36.270Z
---

# [Issue 1640]: [[BUG] Clearing a scaffold knob leaves the previous render in the preserved .pre-commit-config.yaml](https://github.com/vig-os/devkit/issues/1640)

### Description

The scaffold's knob renders mutate `.pre-commit-config.yaml` in place, and that
file is **preserved** across upgrades (`assets/init-workspace.sh:107`, #878 — the
consumer owns its hook excludes). Each render early-returns when its manifest key
is empty:

```bash
render_commit_types() {
    [[ -z "$MANIFEST_COMMIT_TYPES" ]] && return 0
```

So the file is a persistent accumulator of past renders, and an empty key means
*"don't touch it"*, not *"restore the default"*. A consumer who sets a knob, then
**clears** it to go back to the default, keeps the previous render locally forever
— while CI, which re-derives from `.vig-os` on every run with no memory, resolves
the default. Local and CI then disagree about the same gate.

Affects the three renders that write a value into the preserved config:
`render_commit_types` (#1431), `render_branch_types` (#1432), and
`render_refs_policy` (#1282/#1633).

### Steps to Reproduce

1. Scaffold a workspace.
2. Set `DEVKIT_COMMIT_TYPES=feat,fix,record` in `.vig-os`, run the upgrade.
   `.pre-commit-config.yaml` now carries `"--types", "feat,fix,record"`.
3. Clear the key back to `DEVKIT_COMMIT_TYPES=` — which the manifest comment
   documents as "the stock 11 types" — and run the upgrade again.
4. `grep -- --types .pre-commit-config.yaml`.

### Expected Behavior

The hook arg returns to the stock 11 types, matching what `resolve-toolchain`
emits for the same manifest.

### Actual Behavior

The hook arg is still `feat,fix,record`. `record(...): …` passes the local
`commit-msg` hook and fails CI's `validate-commit-range`. The same holds for
`DEVKIT_BRANCH_TYPES` (branch guard) and `DEVKIT_REFS_OPTIONAL_TYPES` /
`DEVKIT_REFS_POLICY` (Refs exemption).

Nothing catches it: the scaffold-drift gate (#1295) re-runs the scaffold and
`git diff`s, so it hits the same empty-key early return, reproduces the stale
file byte-identically, and sees no drift. It detects hand-edits and stale pins,
not a render that was never applied. The upgrade's preserved-file diff against
the template makes it visible, if noticed.

### Environment

Any consumer on any delivery mode; reproduced against `dev`.

### Possible Solution

Make the three renders **unconditional and idempotent**: always write the
resolved value (which for an unset knob is a no-op write of identical bytes, so a
default scaffold stays byte-identical). Two things that makes load-bearing:

1. **A symlink guard is required.** `[[ -f "$pc" ]]` is true for symlinks, and in
   flake-hooks mode `.pre-commit-config.yaml` is a gitignored `/nix/store`
   symlink that materializes on shell entry (#883/#1167, `:1415`). GNU `sed -i`
   replaces a symlink with a regular file, which would silently shadow the
   flake-generated config with a frozen copy — turning a staleness bug into a
   broken opt-in. Every render needs `[[ -L "$pc" ]] && return 0` before the sed.
2. **`render_branch_types` needs a generic anchor.** It is anchored on the
   literal STOCK alternation (`(feature|bugfix|hotfix|release|docs|test|refactor)/[0-9]`),
   so once a custom set has been rendered the anchor no longer matches and the
   stock set can never be restored. It must match whatever alternation currently
   occupies that slot, the way the `[^"]*` value anchors in the other two renders
   already do.

Out of scope: `render_workflow_model`'s `gitflow → trunk` transform has the same
one-way shape (switching back cannot restore the dropped `(?!dev$)` clause), but
it is a set of prose/marker substitutions rather than a single value slot, so it
wants separate treatment.

### Additional Context

Found while reviewing #1633. That PR's first version gated `render_refs_policy`
on the *resolved value* rather than the key, which extended the same failure to a
key that was **set** to a valid value; it was reverted to a key-shaped gate so
refs behaves exactly like its two siblings, and the remaining gap was left for
this issue rather than fixed as a drive-by across three renderers.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 17, 2026 at 07:10 AM_

Shipped to `dev` in #1641 (merge commit 4914a5f6), all 12 checks green.

The three knob renders — `render_commit_types`, `render_branch_types` and
`render_refs_policy` — are now unconditional and idempotent: the resolved value
is written on every run. An unset knob rewrites exactly what the template already
ships, so a default scaffold stays byte-identical and the drift baseline is
untouched; a **cleared** knob now gets the default back instead of stranding the
previous render in the preserved config.

Two things the fix needed beyond dropping the early return:

- **`render_branch_types` needed a generic anchor.** It was anchored on the
  literal stock alternation, which by construction stops matching the moment a
  custom set has been rendered — so making it unconditional alone would have
  fixed nothing there, since the stock set could never be written back. The
  anchor is now the `(?!^(` prefix plus the `)/[0-9]` suffix, which together pin
  exactly that one alternation: the `(chore)/[a-z0-9]` clause has the wrong
  suffix and the `renovate`/`worktree` clauses have no inner group. Verified to
  round-trip byte-identically (stock → custom → stock reproduces the template
  line exactly) before being trusted.
- **One `precommit_render_target` resolver, refusing symlinks**, which is what
  makes the rest safe. `render_workflow_model`'s `.pre-commit-config.yaml` block
  was carrying the same latent hazard and now goes through it too.

Verified with five bats cases committed failing first (`b4963195`) — and the
symlink case failed *after* a successful upgrade, i.e. because the symlink was
genuinely replaced by a regular file, not because the scaffold errored. Full
`bats tests/bats/init-workspace.bats` 266 passed / 0 failed, deliberately
including the #1255 flake-hooks fixtures and the trunk-render composition tests
since this touches shared machinery; `pytest` 1071 passed / 1 skipped;
`prek run --all-files` green with no reformats.

Left out, as flagged in the issue: `render_workflow_model`'s `gitflow → trunk`
transform has the same one-way shape — switching a consumer back cannot restore
the dropped `(?!dev$)` clause or the prose substitutions. It is a set of anchored
substitutions across many files rather than a single value slot, so it needs its
own design rather than this pattern. It does get the symlink guard, since that
hazard is identical.

Closing as done. It reaches consumers with the next release train.

