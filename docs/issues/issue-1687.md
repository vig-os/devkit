---
type: issue
state: closed
created: 2026-09-25T06:18:02Z
updated: 2026-09-25T12:32:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1687
comments: 1
labels: chore, priority:medium, area:ci, area:testing, effort:large, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:47.175Z
---

# [Issue 1687]: [[CHORE] BATS runtime: parallelize the suite, batch the init-workspace.sh fork loops, collapse redundant scaffolds](https://github.com/vig-os/devkit/issues/1687)

### Chore Type

CI / Build change

### Description

The BATS suite is the single largest contributor to CI wall-clock time, and
`Project Checks` is the only job on the critical path.

Measured on run [36052799861](https://github.com/vig-os/devkit/actions/runs/36052799861)'s
predecessor [36050981328](https://github.com/vig-os/devkit/actions/runs/36050981328)
(`Project Checks`, job `107806145241`):

| Step | Duration |
|---|---|
| setup-env (nix dev-shell) | 46s |
| prek linters | 25s |
| **`bats tests/bats/`** | **6m 14s** |
| pytest + coverage | 1m 25s |
| 6 nix/flake steps | 2m 40s |
| **job total** | **11m 28s** |

The whole run is 11m 35s; every other job (Security Scan, Image Tests,
Integration Tests) finishes by 19:58, five minutes before `Project Checks`.
So BATS is ~54% of the long pole and ~50% of end-to-end CI.

Within BATS the cost is one file:

| File | Tests | CI time | Share |
|---|---|---|---|
| `init-workspace.bats` | 300 | **291.9s** | **79.6%** |
| `install.bats` | 95 | 21.2s | 5.8% |
| `just.bats` | 58 | 10.8s | 2.9% |
| `release-mirror-fold.bats` | 11 | 10.2s | 2.8% |
| other 17 files | 136 | 32.6s | 8.9% |

No slow individual test — 300 tests at ~1s each, because they make **~274 full
invocations of `assets/init-workspace.sh`** (114 tests invoke it 0x, 111 once,
63 twice, 12 three or more).

Three independent levers, measured locally on 8 cores. WP1 and WP2 are
behaviour-preserving and touch no test semantics; WP3 is a test refactor.

### Acceptance Criteria

**WP1 — run BATS in parallel**

- [ ] `parallel` (GNU parallel) added to `nix/devtools.nix` (or to the `bats` wrapper in `nix/bats.nix`), so `bats --jobs` resolves wherever the flake toolchain is delivered
- [ ] `.github/actions/test-project/action.yml` runs `bats -j "$(nproc)" tests/bats/` instead of a bare `bats tests/bats/`
- [ ] `just test-bats` drops the per-file `parallel` branch in favour of `bats -j`
- [ ] Full suite green under `-j` in CI (600/600)

**WP2 — batch the two per-file fork loops in `assets/init-workspace.sh`**

- [ ] `sweep_scaffold_writable` collects its targets and issues one batched `chmod u+w` instead of one fork per file
- [ ] The placeholder-substitution fallback uses a single `grep -rlZ ... | xargs -0 sed -i` instead of a per-file `grep -q` + `sed -i` loop
- [ ] A scaffold rendered by the new script is byte-identical to the old one, permissions included (`diff -r` + `find -printf '%m %p'` both clean)
- [ ] `shellcheck -x assets/init-workspace.sh` clean; `just precommit` green
- [ ] `init-workspace.bats` 300/300 green against the changed script

**WP3 — stop re-rendering trees an earlier test already built**

- [ ] A `_clone_shared <mode> <ws>` helper (or equivalent) copies a `setup_file`-rendered tree instead of re-running the script, for tests whose setup is a stock scaffold
- [ ] The identical-setup groups below are collapsed onto it
- [ ] `init-workspace.bats` 300/300 green, and the number of `init-workspace.sh` invocations per full-file run drops measurably (record before/after)

**Cross-cutting**

- [ ] CI `Project Checks` job time recorded before/after in the PR body
- [ ] No test deleted or weakened — this issue is about runtime, not coverage

### Implementation Notes

**WP1.** `.github/actions/test-project/action.yml` runs a bare `bats tests/bats/`
— no `--jobs`. `just test-bats` *tries* to parallelize, but with GNU `parallel`
**one file per job**, and `parallel` is not in `nix/devtools.nix`, so the
`command -v parallel` check always falls through to the sequential branch.
Even if it didn't, file-level parallelism is the wrong axis: 80% of the time is
inside a single file. `bats -j` parallelizes *within* files.

```
bats    tests/bats/init-workspace.bats   10m 09s
bats -j 8 tests/bats/init-workspace.bats  2m 01s   300/300 pass
bats -j 8 tests/bats/                     3m 00s   600/600 pass, exit 0
```

Parallel-safety was checked before measuring: every test writes only into
`BATS_TEST_TMPDIR`/`BATS_FILE_TMPDIR`, the only `$PROJECT_ROOT` touches are
reads, and all podman/gh/just interaction is stubbed. The `setup_file` shared
trees from #1417 still render once per file.

The runner is a 4-vCPU `ubuntu-26.04`, so expect ~2.5-3x there rather than the
5x measured on 8 cores.

**WP2.** Profiling one `init-workspace.sh --mode both` run (4,353 traced
commands, 1.74s total):

| Line | What | Share |
|---|---|---|
| 3479 | `grep -q` per file, placeholder fallback | **42%** |
| 3200 | `chmod u+w` per file in `sweep_scaffold_writable` | **23%** |
| 3175 | the actual `rsync` | 4% |

Both are one fork per file across a 163-file tree. Batching both:

```
per invocation             1770ms -> 604ms   (-66%)
init-workspace.bats, -j 8   2m 01s -> 1m 16s
sequential (CPU time)      10m 14s -> 5m 38s
```

A prototype diff is 10 lines; rendered trees came out byte-identical and all
300 tests passed against it.

Two things worth knowing about the `grep` loop:

- It is the **fallback** branch. The fast `.placeholder-manifest.txt` path
  exists only inside the image (#718/#802 bakes it at `/root/assets/`, and the
  path translation hardcodes `/root/assets/workspace`). Real consumers go
  through `install.sh`, which runs the script *in the container*, so they get
  the fast path. The fallback is effectively a test-only code path — which also
  means the BATS suite never covers the substitution path consumers actually
  run; only `test_image.py::test_placeholder_manifest_baked` does.
- The "fast" manifest path forks one `sed -i` per manifest entry. Measured:
  117 per-file `sed -i` = ~2.6s vs ~0.15s batched, ~15-20x slower. A single
  `grep -rlZ ... | xargs -0 sed -i` — exactly what `flake.nix:1476` already
  uses to *build* the manifest — beats the manifest path outright. Worth
  considering as a follow-up: retiring the manifest, its flake build step, its
  image test and the host/image divergence in favour of one SSoT code path
  that is faster than both. Out of scope here; file separately if wanted.

`sweep_scaffold_writable` is on the production path too, so batching it is a
small consumer-side win as well.

**WP3.** Grouping the 300 tests by byte-identical setup prefix:

| Tests | Identical setup | Redundant runs |
|---|---|---|
| 63 | `mkdir -p "$ws"; _scaffold both "$ws"` | 62 |
| 11 | `_scaffold direnv "$ws"` | 10 |
| 9 | seed `package.json`; `_scaffold both` | 8 |
| 8 | `_upgrade both "$ws"` | 7 |
| 5 | `_scaffold_ex both "$ws" --workflow trunk` | 4 |
| 11 more groups | | 20 |
| | | **111 of ~274 (40%)** |

`_shared_tree` from #1417 exists but is used by only 14 of 300 tests. The
63-test group renders exactly what `setup_file` already builds as
`_shared_tree both`, then mutates it — so it cannot reuse the tree directly,
but it can **copy** it: `cp -a` of the scaffold tree is **36ms vs 1770ms**, and
the render is path-independent (`.vig-os` carries no absolute path; two renders
into different directories diff clean).

Note on TDD: WP1 and WP2 are behaviour-preserving changes with no natural
failing test — the regression net is the existing 600 tests plus the
byte-identical tree/permission diff. WP3 is a test-internal refactor. Any
structural pin added (e.g. asserting the batched form) should be red-first.

### Related Issues

- Follows #1417 (test-suite runtime: shared scaffold fixtures) and #1413 (test-suite pruning). `init-workspace.bats` has grown 238 -> 300 tests since, as #1633/#1640/#1642/#1651/#1656/#1660 each added a scaffold-per-test cluster — WP3 is the same copy-paste accretion regrown.
- Touches the manifest fast path from #718/#802 (see WP2 notes).

### Priority

Medium

### Changelog Category

Changed

### Additional Context

Content health of the suite was checked while measuring and is good — no action
needed, recorded here so it is not re-derived:

- **No duplicate test bodies.** The one exact-body match
  (`select-ghcr-prune-targets` vs `select-rc-draft-releases`) is a false
  positive: different `$SCRIPT`.
- **No dead pins.** Every `$TEMPLATE_DIR`/`$PROJECT_ROOT` path referenced
  either exists or is a deliberate negative assertion.
- **36 tombstone tests** ("requirements.yaml has been retired", "init.sh no
  longer installs packages via apt/brew/dnf/apk", "devc-upgrade recipe is
  gone"). Legitimate regression guards costing ~0 runtime; `init.bats`'s five
  `requirements.yaml` tombstones are the most archaeological.
- **86 negative greps** (`run grep ...` + `assert_failure`) pass vacuously if
  the target file is renamed or deleted. Most have a positive pin elsewhere; a
  few (e.g. `consumer-doctor.bats:82` on `justfile.project`) do not. Low
  severity, zero runtime cost.
- **No file declares `bats_require_minimum_version`**, so every run emits
  `BW02` warnings about flags on `run`. Cosmetic; one line per file if someone
  wants the noise gone.

Expected outcome of WP1+WP2: CI BATS from 6m 14s to roughly 45-70s,
`Project Checks` from 11m 28s to ~5m 45s, total CI from 11m 35s to ~6m — at
which point Security Scan becomes the co-bottleneck and further BATS work stops
paying.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 12:32 PM_

Solved in #1690 (merged to `dev` 2026-09-25, 77e1895e): `bats -j` via GNU parallel riding in the bats wrapper, batched `init-workspace.sh` fork loops, `_clone_shared` fixtures. CI: BATS step 6m14s → 3m11s, `Project Checks` 11m28s → 9m59s (run 36108278820). Every follow-up it predicted has since shipped to `dev` and closed: #1692 (#1702), #1693 (#1707), #1694/#1695/#1696/#1697 (#1709). Remaining spin-offs are tracked separately: #1699, #1700, #1701, #1703, #1704.

