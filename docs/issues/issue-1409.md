---
type: issue
state: closed
created: 2026-08-11T07:08:18Z
updated: 2026-08-11T07:21:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1409
comments: 1
labels: docs
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:09.297Z
---

# [Issue 1409]: [[DOCS] Document the smoke-test final-release human-approval gate and its operational contract](https://github.com/vig-os/devkit/issues/1409)

### Description

The 1.7.0 train replaced the smoke-test listener's self-approval (broken org-wide by vig-os/org-config#122) with a human-approval gate on the final dispatch (#1391, PR #1392). The mechanism is live-proven, but none of it is documented: the operational contract lives only in issue threads and workflow comments.

`docs/CROSS_REPO_RELEASE_GATE.md` — the contract SSoT — has zero mention of the approval gate, and its Receiver Responsibilities section still describes the pre-1.7.0 flow. `docs/RELEASE_CYCLE.md`'s finalization runbook jumps from "verify the dispatch completed" straight to "run promote-release" with no mention of the mandatory human action in between. Since devkit's `release.yml` does not block on downstream state, nothing tells an operator that the smoke repo is waiting for their approval — following the current docs at the next final leg produces a silent 30-minute stall and a gate timeout (exactly what happened on the 1.7.0 final leg, smoke run 31221248513).

Three things need documenting:

1. **The gate itself**: candidate dispatches leave the smoke release PR unapproved (deferred-approval model, #902); the final dispatch pauses at `Gate final release on human approval of release PR`, polling `reviewDecision` for up to 30 min; on timeout, approve the PR and re-run the failed jobs to resume.
2. **The `reviewDecision` dependency**: GitHub only computes `reviewDecision` when the base branch *requires* reviews. Smoke main's `required_approving_review_count: 1` is org-config-owned (vig-os/org-config#127, guarded by an inline comment in `vig-os.jsonnet`) and is part of this gate's contract.
3. **The default-branch listener pitfall**: `repository_dispatch` executes the listener from smoke-test **main**, so listener changes are only live once they reach main. The devkit asset is the SSoT; urgent fixes are hotfixed to smoke main and mirrored in the asset (this has now been needed twice: devkit-smoke-test#345 and #353).

### Documentation Type

Update existing documentation

### Target Files

- https://github.com/vig-os/devkit/blob/main/docs/CROSS_REPO_RELEASE_GATE.md
- https://github.com/vig-os/devkit/blob/main/docs/RELEASE_CYCLE.md

### Related Code Changes

Follows up on #1391 (breakage + design decision), PR #1392 (the gate), #1396 (failure-notify fix), vig-os/org-config#122 (org-wide approval block), vig-os/org-config#127 (required review on smoke main).

### Acceptance Criteria

- [ ] `CROSS_REPO_RELEASE_GATE.md` Receiver Responsibilities describe the candidate (no approval) vs final (human-approval gate) behavior
- [ ] `CROSS_REPO_RELEASE_GATE.md` documents the two contract dependencies: required reviews on smoke main (org-config-owned) and default-branch listener execution (asset SSoT, hotfix-main + mirror procedure)
- [ ] `CROSS_REPO_RELEASE_GATE.md` Failure Signals include the gate timeout and its recovery (approve, then re-run failed jobs)
- [ ] `RELEASE_CYCLE.md` finalization runbook has an explicit step: approve the freshly created smoke release PR when the final dispatch reaches the gate (30-minute window), linking to the gate doc
- [ ] Content cross-references #1391/#1392 and org-config#122/#127

### Changelog Category

Changed

### Additional Context

Out of scope, worth separate issues: (a) fail-fast preflight in the gate (check required-reviews before the 30-min poll) and an awareness ping when the gate starts waiting; (b) `CROSS_REPO_RELEASE_GATE.md` still refers to this repo as `vig-os/devcontainer` throughout — a stale pre-rename name of the same kind that caused #1396.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 07:21 AM_

Solved by PR #1410 (merged to dev). Closing manually — dev-targeted Closes does not auto-close.

