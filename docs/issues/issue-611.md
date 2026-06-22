---
type: issue
state: open
created: 2026-06-22T07:33:09Z
updated: 2026-06-22T07:33:09Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/611
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-22T07:33:16.695Z
---

# [Issue 611]: [Smoke-test dispatch failed for 0.3.7](https://github.com/vig-os/devcontainer/issues/611)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.7`
- release_kind: `final`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `27935851631`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/27935851631
- source_sha: `b02d19acef0bbc2cb6dab94cb8caffb9611c4869`
- correlation_id: `vig-os/devcontainer:27935851631:0.3.7`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/27936603458
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/166
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/167

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `success`
- trigger-release: `failure`
- wait-release-pr-ci: `skipped`
- trigger-promote-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
