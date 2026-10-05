---
type: issue
state: closed
created: 2026-09-28T08:15:07Z
updated: 2026-09-28T09:30:09Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1737
comments: 1
labels: bug, priority:high, area:ci, area:workflow, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:57.330Z
---

# [Issue 1737]: [[BUG] Smoke gate dispatches promote while the finalize sync-issues push is re-running PR CI](https://github.com/vig-os/devkit/issues/1737)

## Description

The cross-repo smoke gate's promote lane races the `sync-issues` commit that
`release.yml`'s `finalize` job pushes, so the listener can dispatch
`promote-release.yml` while the release PR's CI is re-running. Promote then
refuses at `Validate promote prerequisites` with `ERROR: PR #<n> has checks
still in progress`, failing the gate on a timing artifact rather than on
content.

Observed live on the 1.17.0 train (incident record: #1735):

- `devkit-smoke-test` finalize triggered `Sync Issues and PRs` at `06:57:29`
- that push re-triggered the release PR's CI at `06:58:32`
- the listener's `Wait for release PR required checks` job had **already**
  passed against the pre-push check set, so it proceeded
- `Promote Release` validated at `07:02:09`, found the new CI still running,
  and refused (run `36389373270`)

Re-dispatching the same workflow over the same content once CI settled passed
cleanly (run `36392110808`), which is what identifies this as a race and not a
defect in the promoted content.

## Why this is systemic, not a one-off

`finalize` pushes the `sync-issues` commit on **every** train, and that push
always re-triggers the release PR's `pull_request` CI. So the ordering hazard
is structural: `Wait for release PR required checks` can observe a green,
complete check set that a push moments later invalidates. Whether the gate
passes is decided by how the finalize push, the CI queue and the promote
dispatch happen to interleave — it held for the 1.16.0 train and lost for
1.17.0.

The guard itself behaved correctly and should not be loosened: it refuses
*before* the irreversible undraft, which is exactly what stops a published
release that then fails to merge. The bug is upstream of it, in when promote is
dispatched.

## Expected behaviour

The listener does not dispatch promote until the release PR's checks are green
**for the head commit it is about to promote** — i.e. the check-wait is
anchored to a SHA, rather than asking "are checks green now" against whatever
head exists at poll time. A check set that is green for a superseded SHA must
not satisfy the wait.

## Suggested direction (not prescriptive)

Resolve the release-branch head first, then require the green check set to
belong to that SHA, so a later push demotes the wait instead of leaving a stale
pass standing. Related prior art: #1516 (a prepare-time snapshot replayed by a
rerun) and #1487 (validate counting superseded runs) are the same family of
"the signal we checked is not the signal we are about to act on".

## Notes

- Affects the `devkit-smoke-test` listener lane; the equivalent wait in
  devkit's own promote path deserves the same audit, since `finalize` pushes
  `sync-issues` there too.
- Recovery in the meantime is a plain re-dispatch of
  `promote-release.yml` once the PR's CI settles — no content change needed.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 28, 2026 at 09:30 AM_

Fixed on `dev` in #1741 (merge `9bab3bbe`).

The `wait-release-pr-ci` job now holds on two independent conditions per poll iteration:

- **Release-branch quiescence** — no `queued`/`in_progress` run on the PR's own head branch (resolved via `gh pr view --json headRefName`, not reconstructed from the version). This is what spans the `finalize` → `sync-issues` → push chain, since the `Sync Issues and PRs` run is in progress on the branch for its whole life.
- **SHA-anchored check read** — `headRefOid` sampled immediately before and after `gh pr checks`; a mismatch discards the observation with no pass *and no fail/cancel verdict*, so a push landing inside the query window cannot be misread either way.

The confirmed SHA is exposed as `wait-release-pr-ci.outputs.head_sha`, and `trigger-promote-release` carries a last-mile guard that re-reads the head before dispatch and refuses with both SHAs named. `promote-release.yml`'s own `CI_PENDING` refusal was deliberately left untouched — it behaved correctly and is the control that stops a published release that then fails to merge.

**Devkit's own promote path was audited and needs no change** (issue Notes): `finalize` waits synchronously on `sync-issues` within the same job, and promote is human-dispatched via `just promote-release` after the single human approval, so there is no unattended wait-then-dispatch chain to race.

**Still owed before the next final train:** `repository_dispatch` executes the listener from `devkit-smoke-test`'s default branch, so this devkit asset is the source of truth but is **not live** until it reaches smoke-test `main` (precedent: devkit-smoke-test#345, #353). Until then the race can still reproduce.

Residual narrowness, not a defect today: the quiescence gate matches `queued`/`in_progress` but not `waiting` (a run parked for environment approval). `devkit-smoke-test`'s `.vig-os` has `DEVKIT_COMMIT_APP_ENVIRONMENT=` empty, so no run there can enter that state; it would only matter if that key were set.

