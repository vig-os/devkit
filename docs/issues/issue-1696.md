---
type: issue
state: closed
created: 2026-09-25T07:49:58Z
updated: 2026-09-25T10:40:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1696
comments: 2
labels: chore, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:44.894Z
---

# [Issue 1696]: [[CHORE] Settle whether _upgrade into an empty dir equals _scaffold and collapse the remaining redundant renders](https://github.com/vig-os/devkit/issues/1696)

### Chore Type

General task

### Description

After #1687's WP3, the largest remaining cluster of redundant
`init-workspace.sh` renders in `tests/bats/init-workspace.bats` is the
`_upgrade both "$ws"` family: ~13 tests that run the script into an
**empty** directory via `_upgrade` (real `just` on PATH, `uv` stubbed)
purely as setup, then mutate or inspect the tree. WP3 did not convert them
because `_upgrade` differs from `_scaffold` in two ways — real `just` (the
base-recipe repair probes `just --show`) and a stubbed `uv` — and nobody
proved that on an empty directory the resulting tree equals the `both`
fixture.

Either it does, and those sites become `_clone_shared both` (≈13 renders
saved, ~4s under `-j 8`), or it does not, and they get their own
`upgrade-both` fixture in `setup_file`, which saves the same renders.

### Acceptance Criteria

- [ ] The equivalence is settled by evidence: render `_upgrade both` and
      `_scaffold both` into empty directories and compare with `diff -r` +
      `find -printf '%m %y %p'` (the WP2/WP3 proof method); paste the
      verdict in the PR
- [ ] If identical: pure-setup `_upgrade both` sites (empty target, no
      assertion on the run's output/failure, no seeded files) are converted
      to `_clone_shared both`, following WP3's conversion rule verbatim
- [ ] If not identical: an `upgrade-both` fixture is added to `setup_file`
      (rendered the way `_upgrade` renders — real `just`, stubbed `uv`) and
      the same sites clone it
- [ ] Sites whose subject is the upgrade run itself (repair messages,
      `assert_output --partial` on the run, `--separate-stderr`) keep their
      real invocation
- [ ] `init-workspace.bats` 300/300; invocation count before/after recorded
      (the #1687 counting-shim method: 250 after WP3)

### Implementation Notes

- The interesting difference is the `just sync` tail step: `_scaffold`
  stubs `just` (so nothing runs) while `_upgrade` runs the real `just` with
  `uv` stubbed — the recipe executes, `uv sync` is a no-op. Whether that
  leaves any trace in the tree (a `.venv`, a lock, a log) is exactly the
  question.
- Do this after #1695 if the outcome is a new
  fixture, so the extra render is free.

### Related Issues

- Follows #1687 (WP3 left this cluster alone deliberately), PR #1690
- Sibling: #1695 (concurrent `setup_file` renders)

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 10:28 AM_

Settled (PR branch `bugfix/1694-worktree-bats-isolation`): **they are identical.**

`_upgrade both` and `_scaffold both` rendered into empty directories, three rounds each:
`diff -r` clean every time, and `find -printf '%m %y %p' | sort` listings identical every
time. The `just sync` tail step leaves **no** trace in the tree — no `.venv`, no lock, no log.
The only difference is on stdout, the extra line the real `just` prints:

```
> just sync: no pyproject.toml — skipping
```

(plus the workspace-path echo and rsync's byte counters, both trivially path-dependent).

So the first branch applies: the sites become `_clone_shared both`, no `upgrade-both` fixture
is needed.

**One correction to the estimate.** "~13 tests" is too high. Applying WP3's conversion rule
verbatim — empty target, no assertion on the run's output or failure, no seeded files —
exactly **5** of the 35 `_upgrade` sites qualify: the first run of the `#878` stock test
(whose subject is the *second* run) and the four `#886` `--preview` setups. The other 30 seed
a consumer file first (the whole point of an upgrade test) or assert on the run itself.
Invocation count 248 -> 243, not ~237. The saving is smaller than hoped, but the equivalence
verdict is the durable half: it is now recorded in `_clone_shared`'s CONTRACT comment so the
next reader does not re-litigate it.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 10:40 AM_

Shipped to `dev` in #1709. Verdict: identical (diff -r and modes clean, three independent rounds); 5 pure-setup sites converted, invocations 250 → 243; the CONTRACT comment records the proof.

