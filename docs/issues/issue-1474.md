---
type: issue
state: open
created: 2026-08-12T13:55:26Z
updated: 2026-08-12T14:23:20Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1474
comments: 0
labels: docs
assignees: none
milestone: 1.8.1
projects: none
parent: none
children: none
synced: 2026-08-13T04:18:12.031Z
---

# [Issue 1474]: [[DOCS] finalize dismisses the release-PR approval — document the re-approval step before promote](https://github.com/vig-os/devkit/issues/1474)

### Description

`vig-os` now dismisses PR approvals when new commits are pushed. The `finalize` job of a **final** `release.yml` run always pushes to the release branch (the CHANGELOG date stamp, plus the sync-issues commit on top), so **the approval that authorised the final release is destroyed by that very run** — every time, in every repo that consumes the scaffolded release workflow.

`promote-release.yml` then re-checks approvals independently (`.github/workflows/promote-release.yml:435-457`) before merging the release PR into `main`. The result is a mandatory, undocumented re-approval step between the final dispatch and the promote dispatch.

Observed live on the 1.8.0 train today: #1441 was `APPROVED` when `validate` passed at 13:2x, and `DISMISSED` / `REVIEW_REQUIRED` immediately after `finalize` pushed `15abe1b3` + `7a07142d`.

### Steps to Reproduce

1. Approve the release PR and dispatch `release.yml` with `release-kind=final`.
2. Let `finalize` complete (it pushes the date stamp and triggers sync-issues).
3. Read the PR: the approval is `DISMISSED`, `reviewDecision` is `REVIEW_REQUIRED`.
4. Dispatch `promote-release.yml` — its approval gate fails.

### Expected Behavior

The documented procedure tells the operator that the approval will be dismissed by `finalize` and must be renewed immediately before the promote dispatch.

### Actual Behavior

`docs/RELEASE_CYCLE.md` documents the approval as a one-time gate collected before finalization:

- Phase 2 step 7 — *"Mark Ready for Review & Get Approval (gate into finalization) … Because this happens last, the approval lands on the exact diff that ships"*
- Phase 3 Prerequisites — *"PR has required approvals"*
- Phase 4 (promote) does not mention approval renewal at all

Nothing says the approval does not survive Phase 3. An operator following the docs hits a failing promote dispatch with no explanation — the same class of avoidable, mid-promote surprise as the cancelled dispatch in the 1.3.0 train.

### Scope

Not devkit-only. The scaffolded consumer workflow carries the same gate at `assets/workspace/.github/workflows/release-core.yml:294-332`, so every consumer on a repo with stale-review dismissal has the same hidden step. Consumer-facing docs (`docs/DOWNSTREAM_RELEASE.md`) need the same note.

### Possible Solution

**Minimum (the docs fix this issue asks for):**

1. Phase 2 step 7 — note that this approval authorises the final *dispatch* and will not survive it.
2. Phase 3 — state that `finalize` pushes and therefore dismisses approvals where stale-review dismissal is enabled.
3. Phase 4 — add "re-approve the release PR" as an explicit prerequisite, immediately before the promote dispatch, with the reasoning that any later push to the release branch dismisses it again.
4. Mirror into `docs/DOWNSTREAM_RELEASE.md`.

**Design question worth deciding first — should the pre-final approval gate exist at all?**

Arguments for dropping it from `release.yml` and keeping approval only in `promote-release.yml`:

- The signal it carries is now guaranteed to be destroyed by the run it authorises, which makes it a poor carrier for "a human said go".
- The final dispatch is already `workflow_dispatch` — a human necessarily triggered it. The PR approval is not what makes the action deliberate.
- It forces two approvals for one release, the second of which differs only by devkit's own bot commits.
- `promote-release.yml` is where `main` is protected and where `:latest` moves, and it re-enforces approval regardless — the property the gate exists to guarantee is already held there.

Arguments for keeping it:

- The final run burns the **immutable** `X.Y.Z` tag. That is the irreversible step, and gating it on a human review of the exact tree that will be tagged is a real safety property — `validate` runs before `finalize`, so the approved SHA is what gets tagged.
- In a team repo, the dispatcher and the approver can be different people; dropping it collapses a two-person rule into one.
- Consumers inherit this workflow; loosening a release gate for them is a policy change, not a cleanup.

Recommendation: **ship the docs fix now, keep both gates.** The double approval is mildly redundant but each one guards a genuinely different irreversible act (burning the tag; moving `:latest` and merging to `main`). Revisit only if the two-person case is explicitly ruled out for consumers.

### Changelog Category

Changed

Refs: #902, #1392

