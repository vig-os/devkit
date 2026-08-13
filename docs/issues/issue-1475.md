---
type: issue
state: closed
created: 2026-08-12T13:59:17Z
updated: 2026-08-13T06:35:32Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1475
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:11.886Z
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
---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 06:35 AM_

Root cause identified and tracked separately.

The only failing job here, \`trigger-promote-release\`, is the signature of #1477: the listener's `Trigger and wait for release workflow` step matched a **stale** run (rc4's, from ~47 min earlier) instead of the run it had just dispatched, returned success in ~1.5 s, and promote was then fired against a repo that had no `1.8.0` release yet — `ERROR: No GitHub Release for tag 1.8.0`.

The 1.8.0 train itself was recovered at the time by re-running the failed jobs once the real release run had finished; devkit 1.8.0 is released and promoted. Nothing actionable remains on this incident record.

Closing as resolved by #1477, which fixes all three `trigger-and-wait` call sites in `assets/smoke-test/.github/workflows/repository-dispatch.yml` by binding the wait to the dispatched run rather than to an ID ordering.

Refs: #1477

