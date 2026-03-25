---
type: issue
state: closed
created: 2026-03-24T15:08:59Z
updated: 2026-03-25T06:49:19Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/430
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:36.673Z
---

# [Issue 430]: [Smoke-test dispatch failed for 0.3.1-rc17](https://github.com/vig-os/devcontainer/issues/430)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc17`
- release_kind: `candidate`
- source_repo: `unknown`
- source_workflow: `unknown`
- source_run_id: `unknown`
- source_run_url: n/a
- source_sha: `unknown`
- correlation_id: `unknown`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496299850
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/79
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/80

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

_Posted on March 24, 2026 at 03:31 PM_

## RCA: smoke-test dispatch failed at downstream `release.yml`

### Summary

The upstream release for `0.3.1-rc17` succeeded. The failure was in **downstream** orchestration: `repository-dispatch` run [#29](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496299850) failed in **`Trigger and wait for release workflow`** because the **`Release`** workflow run [#4](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496632796) failed in **`Release Core / Validate Release Core`** on step **Find and verify PR** ([job log](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496632796/job/68379524129)).

### Root cause

`release-core.yml` (workspace template) **requires** the release PR to have `reviewDecision == APPROVED` before validation passes:

- Source: [`release-core.yml` — “Find and verify PR”](https://github.com/vig-os/devcontainer/blob/main/assets/workspace/.github/workflows/release-core.yml) (`gh pr list` → reject draft, reject non-`APPROVED`, reject failed CI rollup).

The smoke-test **`repository-dispatch.yml`** flow **never approves** the release PR: it locates the PR, marks it ready, applies `release-kind:*`, then immediately dispatches `release.yml` on `dev`. There is no `gh pr review --approve` (or equivalent) step.

So when **Release** ran, PR [#80](https://github.com/vig-os/devcontainer-smoke-test/pull/80) was open and ready but had **no reviews** → `reviewDecision` was not `APPROVED` → **Find and verify PR** exited non-zero.

### Failure chain

1. Dispatch [#29](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496299850): through **`Prepare release PR`** = success (PR #80 found, ready, labeled).
2. **`Trigger and wait for release workflow`**: dispatches `release.yml` on `dev`.
3. Release [#4](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23496632796): **`Validate Release Core`** → **Find and verify PR** → exit **1** (not approved).
4. **`merge-release-pr`** skipped; **`summary`** / notify path opened this issue.

### Suggested fix (automation)

Add a step in [`repository-dispatch.yml`](https://github.com/vig-os/devcontainer/blob/main/assets/smoke-test/.github/workflows/repository-dispatch.yml) (smoke-test template) **after** marking the release PR ready and **before** triggering `release.yml`: approve the PR with the same release app token used for other PR operations (`gh pr review <n> --approve --body "..."`), so behavior matches the human approval gate assumed by `release-core.yml`.

### Immediate remediation

PR [#80](https://github.com/vig-os/devcontainer-smoke-test/pull/80) is in a good state to proceed manually:

1. **Approve** PR #80 (or use `gh pr review 80 --approve` with appropriate permissions), then **re-run** the failed **`Release`** workflow on `dev` with inputs `version=0.3.1` and `release-kind=candidate` (same as the dispatch), **or**
2. Land the automation fix above and **re-dispatch** with a new RC tag once the smoke-test repo has the updated workflow.


