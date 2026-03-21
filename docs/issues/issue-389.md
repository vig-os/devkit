---
type: issue
state: closed
created: 2026-03-20T07:28:41Z
updated: 2026-03-20T08:30:05Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/389
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:46.410Z
---

# [Issue 389]: [Smoke-test dispatch failed for 0.3.1-rc6](https://github.com/vig-os/devcontainer/issues/389)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc6`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23332785630`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23332785630
- source_sha: `ffc4e247695cf46612b6a986b653ccf08e61096f`
- correlation_id: `vig-os/devcontainer:23332785630:0.3.1-rc6`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23333150355
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/42
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `failure`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 20, 2026 at 07:54 AM_

RCA update for `0.3.1-rc6` smoke-test dispatch failure.

## What failed
The downstream orchestration run failed in **`Trigger and wait for prepare-release workflow`** at:

- `gh workflow run prepare-release.yml -f version=\"${BASE_VERSION}\"`

with:

- `HTTP 404: workflow prepare-release.yml not found on the default branch`

Run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23333150355

## Root cause
`repository-dispatch.yml` in `vig-os/devcontainer-smoke-test` still dispatches `prepare-release.yml`, but that workflow is not present in the default-branch workflow registry.  
The repo currently has `release.yml` (and other workflows), not `prepare-release.yml`, so orchestration calls a non-existent target and fails.

## Why it happened
- Orchestration contract drift between dispatch logic and actual workflow files.
- No preflight validation of required downstream workflow IDs/files before dispatch.
- Integration checks did not detect workflow-target mismatch before RC dispatch.

## Impact
- RC orchestration stopped after deploy.
- Deploy PR merged successfully (`#42`), but prepare-release/release orchestration did not run.
- No release PR was created for this dispatch.

## Remediation (apply both)
1. **Fix workflow target + branch ref**  
   Update `repository-dispatch.yml` to trigger the valid workflow entrypoint and run it from `dev` context (e.g., dispatch existing workflow with `--ref dev` as needed by release flow).
2. **Restore compatibility for current contract**  
   Restore/add `prepare-release.yml` (or a compatibility wrapper with that workflow name) so existing dispatch calls do not 404 while transition completes.

## Preventive actions
1. Add a preflight step that verifies all required downstream workflow IDs/files are present before any dispatch.
2. Add CI coverage for orchestration contract (dispatch target names/inputs must match actual `.github/workflows` entries).
3. Document the downstream orchestration interface (workflow IDs, required inputs, expected refs/default-branch assumptions) in a single canonical doc referenced by both repos.

