---
type: issue
state: open
created: 2026-09-28T08:15:07Z
updated: 2026-09-28T08:15:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1737
comments: 0
labels: bug, priority:high, area:ci, area:workflow, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-28T08:33:58.458Z
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

