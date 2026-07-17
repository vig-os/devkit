---
type: issue
state: closed
created: 2026-07-16T14:38:51Z
updated: 2026-07-16T15:08:53Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1151
comments: 1
labels: bug, priority:high, area:ci, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:02.293Z
---

# [Issue 1151]: [promote-release.yml is not dispatchable on a consumer's first release (chicken-and-egg registration)](https://github.com/vig-os/devkit/issues/1151)

## Context

Consumer: vig-os/sync-issues-action, first devkit 1.3.0 release train, promote step.

## Problem

GitHub only registers a `workflow_dispatch` workflow that exists on the **default branch**. `promote-release.yml` typically has no pre-devkit counterpart on `main` (unlike `prepare-release.yml`/`release.yml`, whose legacy filenames may collide and thus be dispatchable) — and the thing that puts it on the default branch is the release-PR merge that **promote itself performs**. Result: `gh workflow run promote-release.yml` → `HTTP 404: workflow not found on the default branch`, and dispatching by numeric ID is impossible because no ID exists.

First-release consumers must promote **manually**: `gh release edit vX.Y.Z --draft=false` → `gh pr merge <release PR> --merge` → best-effort rc-tag cleanup → floating-tag moves. Two follow-on sharp edges:

1. Promote's validate step hard-requires a **still-draft** release and an **open, approved** release PR — so a half-completed manual promote can never be "resumed" by the workflow once registered.
2. See the companion issue on floating tags: the Tag ruleset is (correctly) Release-App-exclusive, so the manual path cannot move `vX`/`vX.Y` without a temporary ruleset bypass.

## Suggested fixes (preference order)

1. A documented **first-release bootstrap runbook** in MIGRATION.md covering the manual promote sequence end-to-end.
2. Or: make `release.yml` (already dispatchable via legacy filename collision, or via the release branch once CI has run there) able to perform promote as a `workflow_call`/input mode on first release.

Related: vig-os/sync-issues-action#106 (first-release deviations log).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 03:08 PM_

Documented via #1155 (merged to dev). docs/MIGRATION.md gains a "First release after migrating to devkit" section with the manual promote runbook (undraft Release → merge release PR → RC cleanup) and the non-resumable caveat. Ships with the next devkit release.

