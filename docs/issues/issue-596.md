---
type: issue
state: closed
created: 2026-06-18T12:07:56Z
updated: 2026-06-19T06:30:24Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/596
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-19T07:20:03.999Z
---

# [Issue 596]: [Smoke-test dispatch failed for 0.3.6-rc1](https://github.com/vig-os/devcontainer/issues/596)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.6-rc1`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `27757301594`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/27757301594
- source_sha: `9446cfa1d617948a91e6985402b8ca6635a8c307`
- correlation_id: `vig-os/devcontainer:27757301594:0.3.6-rc1`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/27758115273
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/156
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `failure`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- wait-release-pr-ci: `skipped`
- trigger-promote-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 19, 2026 at 06:30 AM_

Opened issue #597 

