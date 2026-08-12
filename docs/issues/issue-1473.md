---
type: issue
state: closed
created: 2026-08-12T13:07:45Z
updated: 2026-08-12T13:15:52Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1473
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:33.893Z
---

# [Issue 1473]: [Smoke-test dispatch failed for 1.8.0-rc4](https://github.com/vig-os/devkit/issues/1473)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.8.0-rc4`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `31598021497`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/31598021497
- source_sha: `39cab3b0196c843726b3807b6345e3ac921a89ca`
- correlation_id: `vig-os/devkit:31598021497:1.8.0-rc4`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31599322806
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/360
- release PR: https://github.com/vig-os/devkit-smoke-test/pull/361

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `failure`
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

Resolved — transient infrastructure, no devkit defect.

`Prepare release PR` failed on a GitHub **502 Bad Gateway** returned by `gh pr ready` for smoke release PR devkit-smoke-test#361 (listener run 31599322806). Everything before it had already succeeded: deploy PR #360 merged, cleanup and prepare-release green. The PR simply stayed in draft.

Re-running the failed jobs resumed from that point — no duplicate deploy — and the chain completed `success`: Release PR, Release run and Release CI all green, promote correctly skipped for a candidate.

1.8.0-rc4 is validated end to end. Same transient class as the Rekor timeouts seen on 1.7.0's rc1/rc2.

