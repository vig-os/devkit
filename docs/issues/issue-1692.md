---
type: issue
state: closed
created: 2026-09-25T07:48:51Z
updated: 2026-09-25T09:35:08Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1692
comments: 2
labels: chore, priority:medium, area:ci, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:46.414Z
---

# [Issue 1692]: [[CHORE] Split the serial Project Checks job into parallel lanes](https://github.com/vig-os/devkit/issues/1692)

### Chore Type

CI / Build change

### Description

`Project Checks` is the only job on CI's critical path, and it is a **serial
chain of independent work**. After #1687 halved the BATS step (PR #1690, run
[36108278820](https://github.com/vig-os/devkit/actions/runs/36108278820)),
the job still ran 9m59s while every other job was done by 8m37s.

Measured on that run (`Project Checks`, job `107985706172`), with the
pre-#1687 baseline (run 36050981328) alongside:

| Block | After #1687 | Baseline | Depends on |
|---|---|---|---|
| `setup-env` (nix dev-shell, uv sync, prek cache) | 44s | 45s | — |
| prek linters | 42s | 25s | setup |
| `bats -j 4 tests/bats/` | 3m11s | 6m14s | setup |
| pytest + coverage | 1m18s | 1m25s | setup |
| nix-fast-build Tier 0 | 45s | 26s | setup |
| flake output schema | 29s | 19s | setup |
| dev-shell contracts | 2s | 2s | setup |
| hooks fidelity + services | 35s | 20s | setup |
| capability modules (native) | 1m58s | 1m17s | setup |
| downstream stub + zizmor | 6s | 3s | setup |
| **job total** | **9m59s** | **11m28s** | |

Nothing after `setup-env` consumes another block's output: prek, BATS,
pytest and the nix gates each read the checkout and the warm dev-shell, and
nothing else. The only reason they run serially is that they share one job.
(The nix rows were ~1.5x slower on the #1687 run because the dev-shell
derivation changed and the Tier 0 gate rebuilt it on a Cachix miss; that is
a one-off per derivation change and does not alter the shape.)

Splitting the job into parallel lanes turns the critical path from the
**sum** of the blocks into setup + the **longest** block: roughly
44s + 3m11s ≈ 4m, at the cost of paying the 44s setup once per lane on
separate runners (the repo is public, so minutes are not metered; the CI
already runs 8 jobs and stays well under the Free plan's 20-concurrent cap).

After the split the whole-run bottleneck moves to `Security Scan`
(build-image 1m57s → security-scan 6m28s = 8m25s on the same run), exactly
as #1687 predicted. That is the next lever and is **out of scope here**;
this issue is about `Project Checks` alone.

### Acceptance Criteria

- [ ] `Project Checks` is split into independent jobs that each run
      `setup-env` once and one block: at minimum **lint + pytest**,
      **BATS**, and **flake gates** (the six nix steps); whether prek and
      pytest share a lane is an implementation choice — measure both
- [ ] The `test-project` composite action's `suite` input grows the
      corresponding values (`lint`, `bats`, `pytest`, …) instead of the
      lanes duplicating its step bodies; the composite stays the SSoT for
      each block
- [ ] `summary` (`needs:` + its per-job result lines) and the
      `workflow_dispatch` `test-suite` gate cover every new job, so a red
      lane still fails the run and a dispatch of `project` still runs all
      of them
- [ ] Any required-status-check names in the `main`/`dev` rulesets that
      reference `Project Checks` are updated in `org-config` (check
      `gh api repos/vig-os/devkit/rulesets`) **before** the rename lands,
      or the old job name is kept for the aggregate
- [ ] `Project Checks` critical path recorded before/after in the PR body;
      target ≤ 5 min for the longest lane on a warm cache
- [ ] Ships through the release-neutral lane (#1676): only
      `.github/workflows/**` and `.github/actions/**` change, no consumer
      artifact moves — assert `devShells.default` / `devkitImage` drvPath
      identity as the lane's guard does

### Implementation Notes

- The natural cut is by *runtime environment need*, not by test framework:
  prek and pytest want the dev-shell + `uv sync`; BATS wants the dev-shell
  only (stubbed `just`/`podman`); the nix gates want Nix + Cachix and a
  warm `nix develop`. `setup-env` already has `sync-dependencies` as an
  input, so the BATS and flake lanes can skip the ~1s `uv sync` and the
  prek cache restore.
- BATS is CPU-bound at 4 vCPU (`-j 4` → 3m11s; 8 cores locally → 74s).
  A further split *within* BATS — `init-workspace.bats` on one runner, the
  other 20 files on another — would bring the BATS lane to ~2m, since that
  one file is ~65% of the suite even after #1687's WP3. Optional, measure
  before adding a matrix.
- The coverage summary/upload steps belong with the pytest lane; nothing
  else produces `coverage.xml`.
- `timeout-minutes: 25` on the current job was sized for the serial chain;
  size each lane to its own block (the nix lane still needs headroom for a
  cold Cachix).
- Do NOT parallelize inside one job with backgrounded steps (`&` + `wait`):
  the log interleaves, `set -e` semantics get lost, and a runner has only
  4 vCPU to share — BATS already saturates it.

### Related Issues

- Follows #1687 / PR #1690 (BATS runtime), which recorded the timing tables
  above and predicted this as the next step
- Release-neutral lane: #1676
- `Security Scan` as the post-split bottleneck: not filed; open one when this
  lands and the run time proves it

### Priority

Medium

### Changelog Category

No changelog needed

### Additional Context

The BATS step's ratio on the 4-vCPU runner was 1.96x (6m14s → 3m11s), below
the 2.5-3x extrapolated from 8-core local runs — per-core throughput on the
hosted runner is lower than on the measurement box. Lane-level parallelism
does not have that ceiling: it adds runners rather than sharing one.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 09:22 AM_

Two acceptance criteria need correcting before this lands.

**Rulesets: nothing to change.** The 4th criterion assumes a `main`/`dev` ruleset
names `Project Checks`. `gh api repos/vig-os/devkit/rulesets` says otherwise:

| Ruleset | Required status checks |
|---|---|
| Dev protection (`refs/heads/dev`) | `Test Summary` |
| Release protection (`refs/heads/release/*`) | `Test Summary` |
| Main protection (`refs/heads/main`) | `Test Summary`, `CodeQL Analysis (actions)`, `CodeQL Analysis (python)` |

The aggregate is the only required check, so it absorbs the rename: **no
`org-config` change, and no aggregate job kept for the old name.** What does
matter instead is the `summary` job's own `needs:` set — under `if: always()` a
lane left out of it is invisible to the required check, not merely unchecked.
`tests/test_workflow_summary_gate.py` asserts that set **exactly**, and the fix
updates the set rather than relaxing the assertion to a subset.

**Scope: not `.github/**` only.** The last criterion says only
`.github/workflows/**` and `.github/actions/**` change. The rename also needs:

- `tests/test_workflow_summary_gate.py` — the exact `needs:` set above;
- `tests/test_workflow_zizmor_baseline.py` — it read
  `ci["jobs"]["project-checks"]["steps"]` to find the zizmor gate, which now
  lives in the `test-project` composite's `runs.steps` (it additionally asserts
  the `project-flake` lane exists to run it);
- one line of `docs/WORKFLOW_SECURITY.md`, which names the job running that gate.

All three are consequences of the rename; none is a consumer artifact, so the
"no consumer artifact moves" half of the criterion still holds.

**Lane.** Shipping to `dev`, not through the release-neutral lane (#1676): `main`
does not yet carry #1690's `bats -j` wrapper, so there is no matching base for the
drvPath-identity guard. It reaches `main` with the next train.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 09:35 AM_

Shipped to `dev` in #1702 (merge c492a0ef). First CI run 36118110737: the four lanes ran at 1m36s / 2m14s / 4m08s / 4m49s, longest lane under the 5-minute target, whole run 10m46s → 8m58s. Security Scan is now the run's bottleneck, tracked in #1701.

