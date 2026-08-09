---
type: issue
state: closed
created: 2026-08-07T18:44:43Z
updated: 2026-08-08T19:55:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1391
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-09T03:48:35.345Z
---

# [Issue 1391]: [[BUG] smoke-test dispatch orchestration broken by org-wide workflow-approval block (org-config#122)](https://github.com/vig-os/devkit/issues/1391)

## What happened

During the 1.7.0 train (rc3, devkit run 31200317431→31206200810), the smoke-test dispatch listener (`assets/smoke-test/.github/workflows/repository-dispatch.yml`) failed at **Approve release PR for automated dispatch** (smoke run 31207370105):

```
failed to create review: GraphQL: GitHub Actions is not permitted to approve pull requests. (addPullRequestReview)
```

The step approves the smoke release PR with `GH_TOKEN: ${{ github.token }}`, which requires the repo/org setting *Allow GitHub Actions to create and approve pull requests*. vig-os/org-config#122 (merged 2026-08-07 16:34Z, applied org-wide) deliberately set `can_approve_pull_request_reviews: false` at the org level — repos cannot re-enable it locally. The 1.6.0 train (2026-08-04) predates the hardening, which is why the chain was green then.

Everything before the approve step worked: deploy PR merged with Direnv Smoke green, stale-release cleanup, prepare-release triggered, release PR located and labeled. Everything after was skipped, so no smoke candidate release ran and the upstream notification was attempted.

## Secondary bug: failure notification cannot mint its token

The `Notify upstream on smoke-test dispatch failure` job also failed, at **Generate release app token for upstream issue creation**:

```
RequestError [HttpError]: Not Found
```

so no upstream issue was filed in devkit. Likely the App-token mint requests an installation for `owner: vig-os` + `repositories: devkit` with an App that is not installed on devkit (or the wrong client-id secret is wired). Needs its own diagnosis — this path had probably never been exercised before.

## Design conflict to resolve (maintainer decision)

The org hardening and the autonomous smoke pipeline are now in direct conflict. Options:

1. **Approve with a second App identity** (e.g. the Commit App token, since the release PR is authored by the Release App — an App cannot approve its own PR, but a different App with write access can, and App installation tokens are not subject to the org's Actions-approval block). Keeps the org policy strict and the pipeline autonomous. Preferred candidate.
2. **Drop the approval requirement for the smoke repo's final release gate** — the auto-approval was ceremonial (a bot rubber-stamping a bot), which is exactly what org-config#122 set out to eliminate; the smoke repo is a machine-driven sandbox. Requires a scaffold knob or smoke-specific patch so real consumers keep the human gate.
3. **Re-enable workflow approvals org-wide** — reverts today's hardening; not recommended.

## Workaround used for the 1.7.0 train

Maintainer manually approves the smoke release PR and manually dispatches the smoke `release.yml` legs (candidate + final) and `promote-release.yml`; validation value is unchanged since the rc3 scaffold is already deployed on smoke dev (deploy PR #339).

Refs: vig-os/org-config#122, smoke run 31207370105, deploy PR vig-os/devkit-smoke-test#339, release PR vig-os/devkit-smoke-test#340
---

# [Comment #1]() by [c-vigo]()

_Posted on August 8, 2026 at 07:55 PM_

Resolved for the 1.7.0 train:

- Listener auto-approve replaced by a kind-aware human-approval gate (PR #1392 to release/1.7.0, shipped in 1.7.0; mirrored to smoke dev via devkit-smoke-test#342 and hotfixed to smoke main via devkit-smoke-test#345 — repository_dispatch executes from the default branch). Candidate path live-proven at rc5 (run 31219339055 fully green, PR left unapproved).
- Human approval on smoke main made *required* (org-config#127) so `reviewDecision` computes — the gate's poll signal needs required reviews. Unblocked by the org-config slug fix (org-config#128/#129) after GitHub dropped numeric-id tolerance on /apps/{app_slug}.
- Final leg completed 2026-08-08 morning: smoke 1.7.0 published 07:55Z, devkit promoted 08:39Z.

Still open from this issue: the failure-notify token mint 404 ("Generate release app token for upstream issue creation" → Not Found) — splitting that into its own issue.

