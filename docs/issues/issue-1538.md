---
type: issue
state: closed
created: 2026-08-17T11:15:56Z
updated: 2026-08-17T12:30:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1538
comments: 1
labels: bug, priority:low, area:workflow, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:13.528Z
---

# [Issue 1538]: [[BUG] CI-green gates classify StatusContext entries as forever-pending](https://github.com/vig-os/devkit/issues/1538)

## Description

Follow-up to #1522 (noted in #1537). The CI-green gates classify every
`statusCheckRollup` entry by `.conclusion` — a field only **CheckRun** objects
have. A **StatusContext** (commit status API) carries `state`
(`SUCCESS`/`FAILURE`/`ERROR`/`PENDING`/`EXPECTED`) instead, so any commit
status always lands in the `CI_PENDING` bucket (`conclusion == null`) and holds
the gate open **forever** — a red commit status can never block as failed, and a
green one can never stop counting as pending.

Affects the same six sites #1537 touched: `release.yml` validate, both
`promote-release.yml` gates (devkit + scaffold), and the consumer
`release-core.yml`. The latest-per-name dedup already keys StatusContexts
correctly (`.name // .context`); only the classification is blind to them.

## Blast radius

None today: no vig-os / exo-pet repo publishes commit statuses — everything
reports via the Checks API. This becomes live the day any consumer adds a tool
that uses the status API (several external CI services and bots do).

The behavior is deliberately **pinned, not blessed** by
`tests/test_ci_green_gate.py::test_status_contexts_keep_pending_treatment` —
that pin should be inverted by this fix.

## Proposed fix

Map `state` into the same three counts alongside `conclusion`:
FAILURE/ERROR → `CI_FAILED`, PENDING/EXPECTED → `CI_PENDING`,
SUCCESS → `CI_SUCCESS`. Extend the executable fixtures in
`test_ci_green_gate.py` (7 scenarios x 6 sites idiom) with red/green/pending
StatusContext cases.

Refs: #1522
---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 12:30 PM_

Fixed in #1541 (merged to dev): all six CI-green gates now classify on a normalized verdict (.conclusion // .state), so commit-status FAILURE/ERROR block as failed, SUCCESS counts as success, and PENDING/EXPECTED hold the pending gates. StatusState enum verified via GraphQL introspection; CheckRun has no state field so nothing double-classifies, and in-progress CheckRuns still count pending. The #1537-era pinned test was inverted as prescribed; 7 new scenario families x 6 sites in test_ci_green_gate.py.

