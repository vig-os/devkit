---
type: issue
state: open
created: 2026-08-12T13:59:17Z
updated: 2026-08-12T13:59:17Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1475
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-13T04:18:11.521Z
---

# [Issue 1475]: [Smoke-test dispatch failed for 1.8.0](https://github.com/vig-os/devkit/issues/1475)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.8.0`
- release_kind: `final`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `31601725030`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/31601725030
- source_sha: `15abe1b3ce08b17809168b45cddb12d032654d43`
- correlation_id: `vig-os/devkit:31601725030:1.8.0`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31603474367
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/362
- release PR: https://github.com/vig-os/devkit-smoke-test/pull/363

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `success`
- trigger-release: `success`
- wait-release-pr-ci: `success`
- trigger-promote-release: `failure`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
