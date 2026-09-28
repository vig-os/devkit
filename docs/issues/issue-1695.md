---
type: issue
state: closed
created: 2026-09-25T07:49:43Z
updated: 2026-09-25T10:40:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1695
comments: 1
labels: chore, priority:low, effort:small, area:testing, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:45.212Z
---

# [Issue 1695]: [[CHORE] Render init-workspace.bats shared fixtures concurrently in setup_file](https://github.com/vig-os/devkit/issues/1695)

### Chore Type

General task

### Description

`tests/bats/init-workspace.bats`'s `setup_file` renders seven shared
fixtures (`devcontainer`, `direnv`, `both`, `bare`, `node-both`,
`python-both`, `trunk-both`, since #1687) **serially**, ~0.3s each after
#1687's WP2, before the first test starts. Under `bats -j` that prologue is
pure critical path: no test in the file can run until it finishes, while
the other cores idle.

It is also what makes small fixtures not pay: a fixture for the 2-test
`Cargo.toml` and `nix/module.nix` seed groups would save two parallel
renders but add one serial one, so #1687's WP3 left them alone.

### Acceptance Criteria

- [ ] `setup_file` renders the fixtures concurrently (background the
      `_render_shared` calls, `wait`, and surface every failed fixture's log
      — not just the first)
- [ ] The `Cargo.toml` and `nix/module.nix` seed groups gain fixtures and
      are converted with `_clone_shared`, now that a fixture costs ~0 wall
      time
- [ ] `init-workspace.bats` 300/300 under `bats -j 8` and sequentially;
      `setup_file` wall time recorded before/after in the PR body
- [ ] The per-fixture `.log` files and the "shared <fixture> scaffold failed"
      diagnostics keep working when several fixtures fail at once

### Implementation Notes

- `_render_shared` already writes each fixture's output to
  `$BATS_FILE_TMPDIR/shared-<fixture>.log`, so the renders do not share
  stdout; only the `|| return 1` short-circuit is serial. Collect PIDs,
  `wait "$pid" || failed+=("$fixture")`, then dump the logs of `failed[@]`.
- Each render forks `init-workspace.sh` with a stubbed `just`; seven in
  parallel on a 4-vCPU runner is fine (they are fork-bound, not CPU-bound).
- Keep the fixture list declarative — one line per fixture — so the next
  cluster added by a feature PR (the pattern #1633/#1640/#1642/#1651/#1656/
  #1660 all followed) reaches for a fixture rather than a per-test render.

### Related Issues

- Follows #1687 (WP3 report), PR #1690
- Sibling: #1696 (`_upgrade` ≡ `_scaffold` equivalence)

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 10:40 AM_

Shipped to `dev` in #1709: nine fixtures rendered concurrently in setup_file (~5s → ~0.6s locally), cargo-both and nix-module-both fixtures added, every failed fixture's log surfaced.

