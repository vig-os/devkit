---
type: issue
state: closed
created: 2026-07-16T14:37:51Z
updated: 2026-07-16T15:15:53Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1150
comments: 1
labels: bug, priority:high, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:02.678Z
---

# [Issue 1150]: [release-core.yml: sync-issues dispatch resolves the default-branch workflow; 120s wait too tight and polling unfiltered](https://github.com/vig-os/devkit/issues/1150)

## Context

Consumer: vig-os/sync-issues-action, first devkit 1.3.0 release train. First final `release.yml` run failed at finalize with "Timed out waiting for sync-issues workflow completion" and triggered the automatic rollback.

## Three stacked problems

1. **Dispatch runs the wrong workflow.** `gh workflow run sync-issues.yml -f "target-branch=release/$VERSION"` passes no `--ref`, so GitHub resolves the workflow definition on the **default branch**. Until the first devkit release merges, that is the *pre-devkit* workflow — in our case one whose state cache was permanently stale (created months earlier; its cache-delete step fails with `Resource not accessible by integration`, so every save collides with `Unable to reserve cache`) → every run re-synced ~5 months of history (~2m18s).
2. **`TIMEOUT=120` is too tight even for the devkit workflow.** After pinning the dispatch to the release branch, the devkit sync workflow's first release-branch run (no cutoff cache → 14-day self-heal) still took **3m30s**. The hardcoded 120 s would have failed the fixed setup too.
3. **Polling races.** Both the wait loop and the conclusion check use `gh run list --workflow sync-issues.yml --limit 1` with no `--branch` filter — a concurrent scheduled run can be mistaken for the dispatched one.

## Consumer-side workaround (applied)

vig-os/sync-issues-action#116, PR vig-os/sync-issues-action#117: `--ref "release/$VERSION"` on the dispatch, `--branch "release/$VERSION"` on both polls, `TIMEOUT=600`. Validated live: the retry succeeded.

## Suggested fix

Adopt all three in the shipped `release-core.yml`: `--ref` pin (correct on every run, not just first releases — the sync should run the release branch's workflow, not whatever the default branch carries), branch-filtered polling, and a more generous (or input-configurable) timeout.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 03:15 PM_

Fixed via #1154 (merged to dev). release-core.yml's finalize job now pins the sync-issues dispatch with --ref release/$VERSION, filters both polls with --branch release/$VERSION, and raises the wait ceiling 120s → 600s. Ships with the next devkit release.

