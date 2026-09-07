---
type: issue
state: closed
created: 2026-09-02T07:26:17Z
updated: 2026-09-02T08:41:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1602
comments: 1
labels: chore, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-03T07:05:15.973Z
---

# [Issue 1602]: [[CHORE] Scaffolded ci.yml has no concurrency block — superseded runs keep burning runner slots](https://github.com/vig-os/devkit/issues/1602)

### Chore Type

CI / Build change

### Description

The scaffolded `ci.yml` has no `concurrency` block. A force-push or rapid
follow-up push leaves the superseded run's jobs queued or running to
completion — every lane (lint, test, commit-checks, scaffold-drift, summary)
finishes for a commit that no longer matters.

On a hosted runner that is wasted billed minutes; on a **self-hosted runner
with a small fixed slot pool** it is worse — the stale run's jobs occupy slots
and the replacement run queues behind its own predecessor. Measured on a
3-slot self-hosted consumer, per-job queue times reach 120–250 s under exactly
this kind of burst contention.

The gap is scaffold-internal inconsistency as much as cost: consumers cannot
fix it themselves, because `ci.yml` is a managed file — a hand-added
`concurrency` block fails the `scaffold-drift` gate (#1295) on every PR. The
fix has to land here.

The summary gate is already prepared for it: since #1371, a needed job that
resolves without a verdict (explicitly including "concurrency cancel") trips
the gate red rather than passing silently, so `cancel-in-progress` on
superseded runs composes with the existing semantics instead of fighting them.

### Proposed change

Add to `assets/workspace/.github/workflows/ci.yml` (and devkit's own copy, if
they are separate render paths):

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Notes:

- Keying on `github.ref` groups per-branch: a PR's superseded run is
  cancelled, `main` pushes cancel older `main` runs. If cancelling in-flight
  `main` runs is unwanted (e.g. a consumer gates deploys on the exact-commit
  run), gate it: `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.
  That conservative form is probably the right default for a scaffold that
  cannot know its consumers' `main`-run semantics.
- `workflow_dispatch` re-runs of the same ref share the group; that is the
  desired behaviour (a dispatched re-test supersedes the previous one).

### Acceptance Criteria

- [ ] Scaffolded `ci.yml` carries a `concurrency` block; superseded
      `pull_request` runs are cancelled
- [ ] In-flight runs for `main` pushes are NOT cancelled by a newer push
      (deploy gates on exact-commit CI green must stay satisfiable)
- [ ] A cancelled superseded run cannot green the summary gate (#1371
      semantics unchanged)
- [ ] Consumers pick it up via the normal adoption PR; no consumer-side edit

### Implementation Notes

One block plus a scaffold test asserting its presence and the
`pull_request`-only cancel condition. `check`-style per-repo workflows outside
the scaffold already do this individually; this closes the gap for the managed
workflow every consumer shares.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 2, 2026 at 08:41 AM_

Shipped to `dev` in #1604 (merge commit `61416cad`), TDD in three commits.

Both `ci.yml` copies now carry:

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```

Both, because they are separate render paths — devkit's own image-building CI
and the mode-aware scaffold consumers receive. #1414 is the standing proof that
a fix landing in one copy only is the likely failure mode here.

### Acceptance criteria

- [x] Scaffolded `ci.yml` carries a `concurrency` block; superseded
      `pull_request` runs are cancelled
- [x] In-flight runs for `main` pushes are NOT cancelled by a newer push
- [x] A cancelled superseded run cannot green the summary gate (#1371
      semantics unchanged)
- [x] Consumers pick it up via the normal adoption PR; no consumer-side edit

### One deviation from the proposed change

The issue suggested gating the cancel as
`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, on the
reasoning that a scaffold cannot know its consumers' `main`-run semantics.
That turned out to guard nothing: **neither copy triggers on `push` at all** —
both run only on `pull_request` and `workflow_dispatch` — so the third
criterion above is satisfied by construction, not by the condition. The
proposed form would have bought no protection while disabling the one case the
issue explicitly wants superseded ("a dispatched re-test supersedes the
previous one").

`!= 'push'` keeps `workflow_dispatch` supersession and still leaves the guard
standing if a `push` trigger is ever added, so a deploy gating on the
exact-commit CI run stays satisfiable.

### Gate interactions, checked rather than assumed

Cancellation touches two existing gates, and neither needed changing:

- **Summary gate (#1371/#1414).** The job is `if: always()` and sets
  `FAILED=true` on `cancelled` for every needed job, in both copies. A
  cancelled superseded run therefore reports FAILURE, not green — the third
  criterion holds without new code. Pinned in `tests/test_workflow_summary_gate.py`.
- **Release-PR CI gate (#1516/#1522).** The inverse hazard: a superseded run's
  entries stay attached to the same head SHA and could refuse a branch that is
  actually green. All six gate sites already group `statusCheckRollup` by check
  name and take `max_by(.startedAt)`, so the live run outranks the cancelled
  one. Pinned in `tests/test_ci_green_gate.py`.

### Verification

New suite `tests/test_ci_concurrency.py`, parametrized over both copies,
pinning the group shape (per-workflow, per-ref) and the exact cancel condition.
RED first — 4/4 failing on `scaffold ci.yml must declare a workflow-level
concurrency block (#1602)` — then green. PR CI: 12/12 pass, `mergeStateStatus:
CLEAN`.

Reaches consumers through the normal `devkit-upgrade` adoption PR once this
lands in a release. Note the issue was not milestoned: there is currently no
open version milestone (only `Backlog` and the closed `1.13.0`).

