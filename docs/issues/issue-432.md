---
type: issue
state: open
created: 2026-03-24T16:28:40Z
updated: 2026-03-24T16:28:40Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/432
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T04:26:16.553Z
---

# [Issue 432]: [Smoke-test dispatch failed for 0.3.1-rc18](https://github.com/vig-os/devcontainer/issues/432)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc18`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23499741825`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23499741825
- source_sha: `27b128975c1a7591e658796ba8ca023e9dd156cb`
- correlation_id: `vig-os/devcontainer:23499741825:0.3.1-rc18`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23500334272
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/84
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/85

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `failure`
- trigger-release: `skipped`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
