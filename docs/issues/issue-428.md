---
type: issue
state: closed
created: 2026-03-24T09:06:48Z
updated: 2026-03-24T09:19:18Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/428
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T04:26:17.249Z
---

# [Issue 428]: [Smoke-test dispatch failed for 0.3.1-rc16](https://github.com/vig-os/devcontainer/issues/428)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc16`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23480376288`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23480376288
- source_sha: `aad2fef4d1f93bb994c51c324aa72790b9cfa3cd`
- correlation_id: `vig-os/devcontainer:23480376288:0.3.1-rc16`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23480922936
- deploy PR: not created
- release PR: not created

## Job results
- validate: `success`
- deploy: `failure`
- wait-deploy-merge: `skipped`
- cleanup-release: `skipped`
- trigger-prepare-release: `skipped`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 24, 2026 at 09:19 AM_

Closing as tracked upstream.

The **re-run** failed with GitHub **secondary rate limit** during the same commit step — caused by one `createBlob` API call per file (~190 calls). Fix is tracked in **vig-os/commit-action#19** (use inline `content` in `createTree`, caveats for binary/large files).

Please follow **vig-os/commit-action#19** for resolution.

