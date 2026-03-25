---
type: issue
state: closed
created: 2026-03-25T10:53:15Z
updated: 2026-03-25T12:36:37Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/438
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:34.398Z
---

# [Issue 438]: [Smoke-test dispatch failed for 0.3.1-rc20](https://github.com/vig-os/devcontainer/issues/438)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc20`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23536456528`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23536456528
- source_sha: `51ad6c63e06622e218a7193edf7c4285d687cedb`
- correlation_id: `vig-os/devcontainer:23536456528:0.3.1-rc20`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23537124050
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/86
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/87

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `success`
- trigger-release: `failure`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 25, 2026 at 10:58 AM_

## RCA — Smoke-test dispatch for `0.3.1-rc20`

### Summary

The failure was **not** in the devcontainer source Release workflow or in the RC image publish for this tag. Smoke-test orchestration progressed through deploy, merge wait, cleanup, `prepare-release`, and "ready release PR", then failed while **waiting for the downstream `Release` workflow** on `dev`.

### Failure chain

1. [Repository Dispatch Listener — run 23537124050](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23537124050): job **Trigger and wait for release workflow** → step **Wait for release workflow completion** → `release workflow concluded with 'failure'`.
2. That run is [Release — 23537271118](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23537271118).
3. Failing job: **Release Core / Validate Release Core** → step **Find and verify PR**.

### Root cause

The validate step failed with:

`ERROR: PR #87 is not approved (status: )`

So the gate requires an **approved** PR in the sense of whatever it reads from the GitHub API (`reviewDecision`), but for [PR #87](https://github.com/vig-os/devcontainer-smoke-test/pull/87) the aggregated **`reviewDecision` was empty** even though **`github-actions` had already submitted an `APPROVED` review** as part of the same orchestration. That usually means a **mismatch between the workflow's check and GitHub's `reviewDecision` semantics** (e.g. protection rules / who counts as an approver), not that the RC tag failed to deploy.

Rollback / tracking: [devcontainer-smoke-test#88](https://github.com/vig-os/devcontainer-smoke-test/issues/88).

### Likely fix (downstream repo)

Adjust **`vig-os/devcontainer-smoke-test`** release validation (or branch protection / bot approval rules) so the **Find and verify PR** step accepts the same approval signal the orchestration actually produces—either by fixing how approval is verified (e.g. not relying solely on `reviewDecision` when rules don't populate it) or by aligning protection rules with the automated approver.

### Not the root cause

- [Source Release run 23536456528](https://github.com/vig-os/devcontainer/actions/runs/23536456528) / tag `0.3.1-rc20` as the **primary** failure point for this incident — the break is in **smoke-test's Release validation** after a successful-looking prepare path.


