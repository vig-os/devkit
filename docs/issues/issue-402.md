---
type: issue
state: open
created: 2026-03-20T14:54:49Z
updated: 2026-03-20T17:09:38Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/402
comments: 2
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:44.036Z
---

# [Issue 402]: [Smoke-test dispatch failed for 0.3.1-rc9](https://github.com/vig-os/devcontainer/issues/402)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc9`
- release_kind: `candidate`
- source_repo: `unknown`
- source_workflow: `unknown`
- source_run_id: `unknown`
- source_run_url: n/a
- source_sha: `unknown`
- correlation_id: `unknown`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23348273354
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/49
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/50

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `failure`
- trigger-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 20, 2026 at 04:34 PM_

## Root Cause Analysis

### Failure

The `ready-release-pr` job failed at step **"Mark release PR ready and approve"** with:

```
failed to create review: GraphQL: Review Can not approve your own pull request (addPullRequestReview)
```

[Failing job log](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23348273354/job/67920335922)

### Cause chain

1. **`trigger-prepare-release` job** dispatches `prepare-release.yml` using the `RELEASE_APP` token (line 445 of `repository-dispatch.yml`). This means `prepare-release.yml` runs with `vig-os-release-app[bot]` as the triggering actor.

2. **`prepare-release.yml`** creates release PR [#50](https://github.com/vig-os/devcontainer-smoke-test/pull/50) using `${{ github.token }}`. Because the workflow was dispatched by the release app, `GITHUB_TOKEN` acts on behalf of `vig-os-release-app[bot]` — so the PR author is `vig-os-release-app[bot]`.

3. **`ready-release-pr` job** then generates a token from the same `RELEASE_APP` and runs `gh pr review "${PR_NUMBER}" --approve` (line 565). This is `vig-os-release-app[bot]` trying to approve its own PR.

4. **GitHub rejects** the self-approval, which is a platform constraint that cannot be overridden.

### Root cause

The workflow uses a single GitHub App identity (`vig-os-release-app`) for both **creating the release PR** (indirectly, via triggering `prepare-release.yml`) and **approving it**. GitHub does not allow a user or bot to approve their own pull request.

### Fix options

| Option | Description | Impact |
|--------|-------------|--------|
| **A. Use `COMMIT_APP` to trigger `prepare-release.yml`** | Change line 445 to use a token generated from `COMMIT_APP_ID`/`COMMIT_APP_PRIVATE_KEY` instead of `RELEASE_APP`. The PR would then be authored by the commit app bot, and the release app can approve it. | Minimal change; requires `COMMIT_APP` to have `actions: write` permission on the smoke-test repo. |
| **B. Use a separate app for approval** | Add a second `create-github-app-token` step in the `ready-release-pr` job that generates a token from `COMMIT_APP`, and use that token for the `gh pr review --approve` call. | Minimal change; requires `COMMIT_APP` to have `pull_requests: write` permission. |
| **C. Skip self-approval if not required** | If branch protection doesn't strictly require an approving review, remove the `gh pr review --approve` call entirely and rely on auto-merge once CI passes. | Zero new permissions; only viable if branch protection allows it. |

Option **B** is likely the cleanest fix — it keeps the release app as PR author and uses the commit app only for the approval, with no change to the dispatch chain.

### Manual cleanup for this run

- Release PR [#50](https://github.com/vig-os/devcontainer-smoke-test/pull/50) is open with `mergeable_state: dirty` (merge conflicts from the changelog sync). It should be closed.
- Branch `release/0.3.1` should be deleted.
- Re-dispatch with a new RC tag after the fix is applied.

---

# [Comment #2]() by [c-vigo]()

_Posted on March 20, 2026 at 05:09 PM_

Scope update: implementation will include both #402 and #398 because they are coupled in the release path.

- #402: split `repository-dispatch.yml` into two phases (dispatch phase and release-on-PR-merge phase), remove the self-approval/merge-wait bottleneck, and preserve automatic failure reporting.
- #398: fix `sync-main-to-dev.yml` to create sync branches via `git push` so CI triggers correctly on PR open.

This keeps the current issue focused on orchestration reliability. The downstream CHANGELOG reset/scaffold behavior is tracked separately in #403 and is intentionally excluded from this change set.

