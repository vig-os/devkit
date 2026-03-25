---
type: issue
state: closed
created: 2026-03-25T09:44:40Z
updated: 2026-03-25T10:19:23Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/436
comments: 0
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:34.822Z
---

# [Issue 436]: [Smoke-test dispatch failed for 0.3.1-rc19](https://github.com/vig-os/devcontainer/issues/436)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc19`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23534073351`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23534073351
- source_sha: `1aafb813dbb6a83927e6d1c5dc2aea52ec3b7f2d`
- correlation_id: `vig-os/devcontainer:23534073351:0.3.1-rc19`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23534621212
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
