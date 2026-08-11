---
type: issue
state: closed
created: 2026-08-10T12:37:14Z
updated: 2026-08-10T12:38:00Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1401
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:26.418Z
---

# [Issue 1401]: [Smoke-test dispatch failed for 9.9.9-rc1](https://github.com/vig-os/devkit/issues/1401)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `9.9.9-rc1`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `manual-live-proof`
- source_run_id: `unknown`
- source_run_url: n/a
- source_sha: `unknown`
- correlation_id: `live-proof-issue-1396`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31388831771
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

_Posted on August 10, 2026 at 12:38 PM_

Synthetic failure — this was the deliberate live-proof for #1396: a `smoke-test-trigger` dispatch with nonexistent tag `9.9.9-rc1` (correlation_id `live-proof-issue-1396`) sent to exercise the notify path after deploying the fix to smoke-test `main` (vig-os/devkit-smoke-test#353). The deploy job failed as intended (no such install URL), and this issue being filed is the proof that the notify job can now mint its upstream App token. No cleanup needed: the run failed before creating any branch or PR. Closing.

