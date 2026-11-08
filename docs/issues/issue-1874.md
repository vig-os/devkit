---
type: issue
state: open
created: 2026-10-12T12:37:57Z
updated: 2026-10-12T17:53:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1874
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:41.949Z
---

# [Issue 1874]: [release-core: test job timeout is fixed at 20 min (no input); consumer releases cancel after Finalize](https://github.com/vig-os/devkit/issues/1874)

**Problem:** `release-core.yml`'s `test` job hard-codes `timeout-minutes: 20` and runs `just test`. A consumer whose suite takes 15–20 min on hosted runners gets its final release cancelled in "Test Finalized Release". Validate and Finalize have already succeeded by then, and Publish is skipped. There is no input to raise the budget or to select a release-test subset.

**Evidence** (exo-pet/MPECT, devkit release pipeline, 2026-10-12):
- run https://github.com/exo-pet/MPECT/actions/runs/38246773280, `Release Core / Test Finalized Release`;
- `Run tests` 12:16:08 → 12:35:16Z, then cancelled at the job timeout. Toolchain 61 s, sync 1 s.
- On the same day, MPECT's normal CI `Tests` job took 14m00s (run 38197859774), also under a 20-min ceiling.

**Ask:** a `release-test-timeout-minutes` input (or `vars.*`) for `release.yml` → `release-core.yml`, defaulting to 20. Optionally a `release-test-command` override, e.g. `just test -m "not slow"`, so consumers can gate releases on a defined subset. Document how a timed-out test job interacts with the finalized `release/X.Y.Z` branch: can `release.yml` be re-dispatched without re-finalizing?

---

# [Comment #1]() by [gerchowl]()

_Posted on October 12, 2026 at 05:53 PM_

A cancelled Test step after Finalize needs abandon + re-prepare.

In exo-pet/MPECT, final run https://github.com/exo-pet/MPECT/actions/runs/38246773280 finalized the 0.1.0 CHANGELOG date, then the hard-coded 20-minute Test Finalized Release job limit cancelled the suite. Publishing was skipped and no tag/GitHub Release was created. The rollback guard handles failure but not cancellation, so the dated release branch remained.

After landing a fast/slow test partition on main (#131) and backporting it into the release train (#133), a new final dry run https://github.com/exo-pet/MPECT/actions/runs/38286625259 failed at `prepare-changelog validate`: the dated entry no longer satisfies the required `[0.1.0] - TBD` heading.

We are recovering through `abandon-release.yml` followed by `prepare-release.yml`, then final release. Alongside a configurable test-job timeout, please consider documenting this cancellation recovery path and/or making rollback/retry handle cancelled test jobs safely.


