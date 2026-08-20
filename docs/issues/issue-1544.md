---
type: issue
state: closed
created: 2026-08-17T14:50:41Z
updated: 2026-08-18T06:25:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1544
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-19T03:04:35.433Z
---

# [Issue 1544]: [[BUG] gh-issues PR table is blind to StatusContexts: name-only grouping and conclusion-only rendering](https://github.com/vig-os/devkit/issues/1544)

## Description

Follow-up to #1539 (found during #1542, noted in its PR body) — the two remaining
StatusContext gaps in `packages/vig-utils/src/vig_utils/gh_issues.py`, the
display-table analogues of what #1538/#1541 fixed in the release gates:

1. **Name-only grouping.** `_dedupe_status_checks` groups on
   `check.get("name") or "?"`, but StatusContexts carry `context`, not
   `name` — every commit status on a PR collapses into one `"?"` bucket and
   only the newest survives the dedup. The gates use `.name // .context // "?"`
   (#1537); the table should match. (The recency key already handles them:
   `_started` falls back to `createdAt` since #1542.)

2. **Conclusion-only rendering.** `_format_ci_status` classifies each entry by
   `conclusion` — a CheckRun-only field — so a red commit status
   (`state: FAILURE`/`ERROR`) renders as pending (⏳), never as failed (✗),
   and a green one (`state: SUCCESS`) never counts toward the pass tally.
   Same normalized-verdict fix as the gates: `conclusion or state`, with
   `EXPECTED` treated as pending.

## Blast radius

Latent: zero StatusContext entries across the last 40 devkit PRs (checked during
#1542) — nothing in the org publishes commit statuses. Display-only when it does
become live (`just gh-issues` table, no gate behavior).

## Acceptance

With a rollup mixing CheckRuns and StatusContexts:
- two distinct StatusContexts survive dedup as two rows' worth of counts (no
  "?"-bucket collapse), and a StatusContext sharing a CheckRun's name/context
  key groups exactly as the gates do;
- a `state: FAILURE` StatusContext renders the CI cell red (✗), `SUCCESS`
  counts as passed, `PENDING`/`EXPECTED` render pending;
- CheckRun-only rollups render exactly as today (regression pins).

Refs: #1539
---

# [Comment #1]() by [c-vigo]()

_Posted on August 18, 2026 at 06:25 AM_

Fixed in #1545 (merged to dev): _check_key (name or context) now drives both the dedup grouping and the failed-names cell, and _verdict (conclusion or state) drives the pass/fail tallies — mirroring the release gates' jq exactly, including tie behavior. Bonus fix: present-but-null names no longer render as None in the red cell. PENDING/EXPECTED and all CheckRun-only rendering unchanged (regression-pinned). CI needed three attempts due to the 2026-08-17 GitHub outage (codeload.github.com 502/503/429 during action download — runners never reached our steps); attempt 3 fully green.

