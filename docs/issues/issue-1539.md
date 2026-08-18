---
type: issue
state: closed
created: 2026-08-17T11:15:58Z
updated: 2026-08-17T12:49:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1539
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:13.084Z
---

# [Issue 1539]: [[BUG] gh-issues PR table dedups check runs on completedAt, ranking live re-runs oldest](https://github.com/vig-os/devkit/issues/1539)

## Description

Follow-up to #1522 (noted in #1537). The `just gh-issues` PR table has its own
latest-per-name check dedup, `_dedupe_status_checks` in
`packages/vig-utils/src/vig_utils/gh_issues.py` (from #176), but it keys
recency on `completedAt` — which is **null while a run is in flight**. A
re-run in progress therefore ranks as the *oldest* run of its name, and the
table shows the superseded FAILURE instead of the live re-run.

This is exactly the pitfall #1537 avoided in the release gates by keying on
`startedAt` (set at creation, never null). Same one-line class of fix here,
plus a test: an in-progress re-run over an older FAILURE of the same name must
surface as the in-progress run.

## Blast radius

Cosmetic only — this feeds a display table, not a gate. But it shows the wrong
verdict during exactly the window someone is watching a re-run, which is when
the table gets read.

## Proposed fix

Switch the recency key to `startedAt` (or a null-safe
`startedAt // completedAt`), mirroring the #1537 gate expression, and pin with
a unit test in `packages/vig-utils/tests`.

Refs: #1522
---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 12:49 PM_

Fixed in #1542 (merged to dev): _dedupe_status_checks now keys recency on startedAt (with createdAt fallback for StatusContexts), mirroring the #1537 gate expression, so an in-flight re-run surfaces instead of the superseded FAILURE. Tie-breaking and the #176 no-timestamp behavior preserved. Two further latent StatusContext gaps in the same file were found and left out of scope (noted in the PR body): name-only grouping collapses commit statuses into one bucket, and _format_ci_status renders a red commit status as pending — the display-table analogues of #1538.

