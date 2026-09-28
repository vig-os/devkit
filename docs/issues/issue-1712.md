---
type: issue
state: closed
created: 2026-09-25T14:33:30Z
updated: 2026-09-25T17:46:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1712
comments: 2
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:41.027Z
---

# [Issue 1712]: [[BUG] Release-neutral guard leaves a stale verdict when a label-event run times out](https://github.com/vig-os/devkit/issues/1712)

### Description

Gate 6 of `.github/workflows/release-neutral-guard.yml` runs under `!cancelled()` (#1705), so a gate failure or an `unlabeled` event now rewrites the sticky verdict comment. One residual of the same class remains: the job carries `timeout-minutes: 90` (budgeted for the vulnix extra), and a job that hits its timeout is **cancelled** — `cancelled()` is true, gate 6 is skipped, and the last positive verdict stands.

For code events the skip is the right call in the common case (a run superseded by a newer head reached no conclusion). For label events it is not: `labeled`/`unlabeled` runs live in a per-`run_id` concurrency lane and can never be superseded, so a cancelled label-event run is a timeout, not a supersession, and the PR is left with a stale positive verdict exactly as before #1705.

### Steps to Reproduce

1. Open a lane PR, let the guard pass (verdict comment posted)
2. Push a commit whose gate 2 or vulnix extra exceeds 90 minutes (or lower `timeout-minutes` to reproduce), or relabel the PR to trigger a label-event run that times out
3. The verdict comment still says release-neutral

### Expected Behavior

A timed-out run rewrites the verdict as "nothing is proved" (infrastructure), at least for label-event runs, which cannot be superseded.

### Actual Behavior

Gate 6 is skipped on `cancelled()`; the positive verdict stands.

### Environment

- **OS**: n/a
- **Container Runtime**: n/a
- **Image Version/Tag**: n/a
- **Architecture**: n/a

### Additional Context

Raised in the #1705 review. Widening the `if:` alone (`!cancelled() || github.event.action == 'labeled' || github.event.action == 'unlabeled'`) is not enough: the outcome scan in gate 6 looks for the first `failure`, and a timed-out step's outcome is `cancelled`, so the widened step would fall through to the **green** body. The scan must treat any outcome other than `success`/`skipped` as non-green and word a `cancelled` gate as an infrastructure failure (timeout).

### Possible Solution

- `if: ${{ (!cancelled() || github.event.action == 'labeled' || github.event.action == 'unlabeled') && (env.ACTIVE == 'true' || env.DEACTIVATED == 'true') }}`
- In the outcome scan, pick the first entry whose value is neither `success` nor `skipped`; map `cancelled` to the infrastructure wording ("timed out / cancelled before completing")
- Shape test: the `if` names the label actions, and the scan does not match on the literal `failure` alone

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 05:00 PM_

## Triage 2026-09-25: implement, but with step timeouts as the primary fix

GitHub semantics verified: a job `timeout-minutes` expiry cancels the job; the in-flight step's `outcome` is `cancelled`, not `failure`, so gate 6's current `= failure` scan would fall through to the **green** body even if it ran. Post-timeout steps *can* still run inside the 5-minute cancellation window when their `if:` re-evaluates true, so the issue's `if:` widening is mechanically viable — but it is the wrong lever: it would also let a manually cancelled or runner-lost label run overwrite a real verdict with a refusal it never reached, eroding what #1705 bought.

Measured on the one `.vulnixignore` lane run (36101356752): setup 41 s, gate 2 32 s, vulnix extra 129 s, gate 6 1 s. The job's 90 minutes is a cold-NVD worst case borrowed from `security-scan.yml`. No step in the repo carries a step-level `timeout-minutes` today.

**Plan:**

1. Step-level `timeout-minutes` on the long steps — `setup` 10, `gate2` 10, `vulnix` 60 — whose sum stays under the job's 90. A hang then fails the *step* while the job continues; gate 6 runs under the untouched `!cancelled()` with no reliance on the cancellation window.
2. Widen the outcome scan: first entry whose value is neither `success` nor `skipped`; a `cancelled` outcome is worded as infrastructure ("timed out / cancelled before completing").
3. Do **not** widen the `if:` (YAGNI, and harmful for label runs as above) — declined explicitly so the record does not read as a partial implementation.

Shape tests in `tests/test_workflow_release_neutral.py`: the three ids carry integer timeouts whose sum is below the job budget (the load-bearing assertion); the scan no longer matches the literal `failure` alone; `cancelled` maps to `infra=true`. Changelog `Fixed`; one sentence in `docs/RELEASE_CYCLE.md`. The timeout path cannot be exercised live. Effort small.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 05:46 PM_

Fixed in #1721, merged to `dev` (69bc1758): step budgets on the three long steps (10/10/60 < 90) so a hang fails the step and gate 6 still runs; and since the runner reports a step-budget expiry as `failure`, a refusal is now something a gate declares (`refused=true` in `$GITHUB_OUTPUT`) — everything else non-green is worded as infrastructure. The `if:` widening proposed here was declined on purpose: a manually cancelled label run must not have its real verdict overwritten.

