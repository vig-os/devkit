---
type: issue
state: open
created: 2026-03-26T17:39:01Z
updated: 2026-03-26T17:39:01Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/454
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:30.146Z
---

# [Issue 454]: [Smoke-test dispatch failed for 0.3.1-rc25](https://github.com/vig-os/devcontainer/issues/454)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc25`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23602722662`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23602722662
- source_sha: `11bc8e9db642a8f1801118b537db062a3b15609b`
- correlation_id: `vig-os/devcontainer:23602722662:0.3.1-rc25`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23603456323
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/107
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `failure`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
