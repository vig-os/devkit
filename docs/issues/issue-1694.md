---
type: issue
state: closed
created: 2026-09-25T07:49:29Z
updated: 2026-09-25T10:40:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1694
comments: 2
labels: bug, priority:medium, effort:medium, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:45.656Z
---

# [Issue 1694]: [[BUG] worktree.bats runs worktree-clean against the live sibling worktrees directory and deletes real worktrees](https://github.com/vig-os/devkit/issues/1694)

### Description

Four tests in `tests/bats/worktree.bats` (the `worktree-attach` /
`worktree-clean` cases, lines ~17, 96, 128, 156) start **real tmux sessions**
and create issue directories `999994–999999` in the repository's **live**
`<repo>-worktrees` sibling directory, then run `just worktree-clean`. That
recipe (`justfile.worktree` ~L396-401) force-removes **every** entry in the
directory that has no tmux session and `git branch -D`s its branch — it does
not distinguish the test's fixtures from a developer's or an agent's real
worktrees.

The tests `skip` under `CI=true`, so CI never sees this. Locally, any full
`bats tests/bats/` (or `just test-bats`) runs them.

### Steps to Reproduce

1. `git worktree add ../devkit-worktrees/1234-anything -b feature/1234-anything`
   (no tmux session — e.g. a hand-made or agent-made worktree)
2. Make a commit on it, do not push
3. `bats tests/bats/worktree.bats` (or `just test-bats`) with `CI` unset
4. `git worktree list` / `git branch --list 'feature/1234*'`

### Expected Behavior

The suite writes only under `BATS_TEST_TMPDIR` / `BATS_FILE_TMPDIR` and never
touches worktrees or branches it did not create.

### Actual Behavior

The worktree directory is deleted and the branch is gone, with any unpushed
commits. This happened for real on 2026-09-25 during #1687: a local
full-suite run removed three agent worktrees and their branches mid-work.
Nothing was lost only because their commits had already been cherry-picked
elsewhere. Under `bats -j` the same tests also race each other
(`not ok … worktree-clean stopped-only skips worktrees with running tmux
session`), which is why PR #1690 had to opt the file out of within-file
parallelism with `BATS_NO_PARALLELIZE_WITHIN_FILE`.

### Environment

- devkit `dev` at PR #1690, any host with tmux, `CI` unset

### Additional Context

The #1687 spike stated "every test writes only into `BATS_TEST_TMPDIR`"; this
file is the exception it missed.

### Possible Solution

Drive the recipes against a throwaway repository: in `setup_file`, `git init`
a fixture repo under `BATS_FILE_TMPDIR`, copy `justfile.worktree` in, and
point the worktree base (`WT_BASE` or whatever the recipe derives
`<repo>-worktrees` from) at a sibling of that fixture. Then the fixtures
`999994–999999` live in a directory nothing else uses, `worktree-clean` can
only remove test fixtures, the tests can `skip`-free run in CI, and the file
can drop `BATS_NO_PARALLELIZE_WITHIN_FILE` and rejoin within-file jobs.
Red-first: a pin asserting that after the file runs the real
`<repo>-worktrees` directory is unchanged (or that the recipe was invoked
with a `BATS_*_TMPDIR` base).

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 10:28 AM_

Two corrections from the fix (PR branch `bugfix/1694-worktree-bats-isolation`):

**The blast radius is wider than "four tests".** Six of the ten tests pointed at the live
base. `wt-clean alias works for stopped-only and all` has **no** `CI=true` skip at all — it
runs `just wt-clean` and `just wt-clean all` against the real `<repo>-worktrees` on every
run, CI included. It only escaped notice because CI has no sibling worktrees to delete.
`worktree-clean rejects invalid mode` and `worktree-attach errors when neither worktree dir
nor session exists` also ran against the real base (harmless in effect — the recipe exits
before the loop — but they were not isolated either).

**The `CI` skip reason is wrong.** "tmux integration tests require interactive TTY" is not
true: `tmux new-session -d` is explicitly detached and needs no TTY, and tmux is on the CI
PATH via `setup-env` (`nix/devtools.nix` ships it). The skips were load-bearing only as
accidental protection for the shared base. With the fixture base they are gone and the file
runs its full 10 tests with 0 skips both locally and under `CI=true`.

Also: no product knob was needed. `_wt_base` is `../<basename $(git rev-parse
--show-toplevel)>-worktrees` **relative to just's working directory**, so
`just --justfile "$WT_MAIN" --working-directory "$FIX"` on a throwaway fixture repo moves the
whole base to `"$FIX-worktrees"`. `justfile.worktree` and its scaffolded mirror are untouched.
And the `BATS_NO_PARALLELIZE_WITHIN_FILE` opt-out from #1690 could be dropped: the race was
the shared base, not the shared tmux server.

**Where the hazard actually bites.** `_wt_base` is relative to just's working directory, so
the base it resolves to depends on *which checkout you run the suite from*. From the **main
checkout** it is the live `devkit-worktrees/` — every agent and developer worktree, which is
what happened on 2026-09-25. From a **linked worktree** it is `<worktree>-worktrees`
(e.g. `devkit-worktrees/1694-worktrees`), which normally does not exist, so `worktree-clean`
prints "No worktrees to clean" and exits. That asymmetry is why the bug survived: an agent
working in its own worktree could run the full suite all day and see nothing, while the same
command from the main checkout deletes the fleet. It also means "run the suite from a
worktree" was never a fix — only a place the blast radius happened to be empty.

One more thing the fix had to cover, found while proving the guard: the guard as first written
protected the *recipe* invocations, but `_wt_fixture` itself does `git init` + `git add -A` +
`commit` inside its target. Pointed at a real checkout it stages that developer's whole tree
before any recipe runs (the commit is then rejected by the commit-msg hook, which is the only
reason it stops there). The guard therefore runs inside `_wt_fixture`, before `git init`, not
just before the recipes.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 10:40 AM_

Shipped to `dev` in #1709: every recipe runs against a per-test fixture repo under BATS_TEST_TMPDIR behind a red-first guard; the tmux tests now run in CI (606/606, 0 skips on run 36124206119). The bats teardown_file exit-0 hole found on the way is #1699.

