---
type: issue
state: closed
created: 2026-08-13T14:43:26Z
updated: 2026-08-13T20:21:57Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1500
comments: 2
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-14T04:14:24.385Z
---

# [Issue 1500]: [Smoke-test dispatch failed for 1.9.0-rc1](https://github.com/vig-os/devkit/issues/1500)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.9.0-rc1`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `31709601077`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/31709601077
- source_sha: `84241bbd2631ef773dde350d351550b19936a254`
- correlation_id: `vig-os/devkit:31709601077:1.9.0-rc1`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31710999351
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

_Posted on August 13, 2026 at 02:45 PM_

Root cause: a burst of GitHub-side 5xx errors on PR mutations between ~14:36 and ~14:43 UTC, not a defect in 1.9.0-rc1 or in the listener.

Three distinct failures, each with its own GitHub reference id:

| attempt | step | error |
|---|---|---|
| 1 | `Create deploy PR` | `pull request update failed: GraphQL ... BC41:387E8A:D18436:2C6E32A:6A7DD680` |
| 2 | `Close stale deploy PRs` | `API call failed: non-200 OK status code: 502 Bad Gateway` |
| 3 | `Create deploy PR` | `pull request create failed: GraphQL ... A040:38004:E68748:30AD048:6A7DD7FC` |

My own `gh` calls from a workstation were taking HTTP 500/502 in the same window (`rerun-failed-jobs`, `issue edit`), which is what rules out the workflow as the source. githubstatus reported "All Systems Operational" throughout — the status page lagged the incident.

Attempt 1 additionally left an **unlabeled** deploy PR that the label-based cleanup could not reclaim, so the documented re-run recovery dead-ended until I added the label by hand. That is a real latent gap and is filed separately as #1499.

Upstream state is unaffected: devkit's own `release.yml` run for 1.9.0-rc1 completed green (both arches built and tested, tag at the release head, multi-arch manifest published), and the RC image has been validated by hand. Retrying the listener.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 13, 2026 at 08:21 PM_

Closing as not-planned, matching the #1475 precedent for auto-filed dispatch incidents.

The cause was a GitHub-side 5xx burst, not a devkit defect — full evidence in the comment above. The 1.9.0 train completed: released and promoted at 15:41:34Z, `:latest` moved, release PR #1498 merged, sync PR #1501 merged conflict-free.

The one actionable finding this exposed — a partially-created deploy PR being invisible to the label-based stale-PR cleanup — is tracked separately in #1499.

