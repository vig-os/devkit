---
type: issue
state: closed
created: 2026-08-12T08:35:40Z
updated: 2026-08-12T13:15:40Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1442
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:41.566Z
---

# [Issue 1442]: [Smoke-test dispatch failed for 1.8.0-rc1](https://github.com/vig-os/devkit/issues/1442)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.8.0-rc1`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `31577466626`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/31577466626
- source_sha: `fc76b521092d9154c0a66e81210b56347bffebf7`
- correlation_id: `vig-os/devkit:31577466626:1.8.0-rc1`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31578823294
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/356
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
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 01:15 PM_

Resolved. Root-caused as #1443: the smoke deploy published via commit-action, which builds its tree additively and cannot express deletions, so the retired `renovate-changelog-*.yml` workflows survived on the deploy branch and `Scaffold Drift` (correctly) rejected the PR.

Fixed by the deletion-publishing step added in #1443 and redeployed to the smoke listener. Retirement now lands on the deploy branch as intended — verified at 1.8.0-rc4, whose deploy PR (devkit-smoke-test#360) removed exactly those two paths and nothing else.

