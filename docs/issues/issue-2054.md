---
type: issue
state: open
created: 2026-11-06T02:47:22Z
updated: 2026-11-06T02:47:22Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/2054
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T09:11:25.489Z
---

# [Issue 2054]: [Smoke-test dispatch failed for 1.19.0-rc4](https://github.com/vig-os/devkit/issues/2054)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.19.0-rc4`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `42147999720`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/42147999720
- source_sha: `865cd3cf9c3206c2326bbd6aeb4f5fb1c43a7789`
- correlation_id: `vig-os/devkit:42147999720:1.19.0-rc4`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/42150667770
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/461
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
