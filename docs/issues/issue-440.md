---
type: issue
state: closed
created: 2026-03-25T12:40:53Z
updated: 2026-03-25T13:01:47Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/440
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:33.929Z
---

# [Issue 440]: [Smoke-test dispatch failed for 0.3.1-rc21](https://github.com/vig-os/devcontainer/issues/440)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc21`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23540969720`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23540969720
- source_sha: `a1bcd94c162e2ba9c5f04fb0f95470a223a85004`
- correlation_id: `vig-os/devcontainer:23540969720:0.3.1-rc21`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23541441516
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

_Posted on March 25, 2026 at 01:01 PM_

Missing manual deployment of latest workflows, fixed [here](https://github.com/vig-os/devcontainer-smoke-test/pull/89)

