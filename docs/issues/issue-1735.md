---
type: issue
state: closed
created: 2026-09-28T07:03:04Z
updated: 2026-09-28T08:15:43Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1735
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-28T08:33:58.821Z
---

# [Issue 1735]: [Smoke-test dispatch failed for 1.17.0](https://github.com/vig-os/devkit/issues/1735)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.17.0`
- release_kind: `final`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `36387071443`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/36387071443
- source_sha: `5d60804b30adbdfaff06c28f958cccde1f6fd15a`
- correlation_id: `vig-os/devkit:36387071443:1.17.0`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/36388454534
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/430
- release PR: https://github.com/vig-os/devkit-smoke-test/pull/431

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
---

# [Comment #1]() by [c-vigo]()

_Posted on September 28, 2026 at 08:15 AM_

Resolved: the 1.17.0 smoke gate completed on a re-dispatch of `promote-release.yml` with no content change — run [36392110808](https://github.com/vig-os/devkit-smoke-test/actions/runs/36392110808), 4/4 jobs green. `devkit-smoke-test` `1.17.0` published 2026-09-28T07:32:38Z and its release PR #431 merged, which satisfied devkit's promote precondition; devkit `1.17.0` was then promoted (GHCR `:latest` moved, release published, PR #1734 merged to `main`).

The original failure was a timing race, not a content defect: the failing run [36389373270](https://github.com/vig-os/devkit-smoke-test/actions/runs/36389373270) refused at `Validate promote prerequisites` with `PR #431 has checks still in progress`, because the `sync-issues` commit that `finalize` pushes had re-triggered the release PR's CI *after* the listener's check-wait had already passed. The guard behaved correctly — it refused before the irreversible undraft.

Because that push happens on every train, the ordering hazard is structural rather than bad luck. Tracking the fix in #1737; closing this incident record.

