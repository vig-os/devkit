---
type: issue
state: open
created: 2026-11-04T13:29:36Z
updated: 2026-11-04T13:29:36Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/2044
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:46.323Z
---

# [Issue 2044]: [Smoke-test dispatch failed for 1.19.0-rc3](https://github.com/vig-os/devkit/issues/2044)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.19.0-rc3`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `41834507704`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/41834507704
- source_sha: `3e9616c6a04d150f81690c3ea94b40087c66062f`
- correlation_id: `vig-os/devkit:41834507704:1.19.0-rc3`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/41836403209
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/460
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `failure`
- cleanup-release: `skipped`
- trigger-prepare-release: `skipped`
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
