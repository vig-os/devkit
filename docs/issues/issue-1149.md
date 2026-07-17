---
type: issue
state: closed
created: 2026-07-16T14:37:49Z
updated: 2026-07-16T15:00:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1149
comments: 1
labels: bug, priority:medium, area:ci, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:03.040Z
---

# [Issue 1149]: [validate-commit-range: first release train re-lints pre-gate history and blocks the release PR](https://github.com/vig-os/devkit/issues/1149)

## Context

Consumer: vig-os/sync-issues-action, first release train after adopting devkit 1.3.0 (direnv mode; pilot-follower of vig-os/commit-action#32).

## Problem

The `Commit Messages` job in the scaffolded `ci.yml` validates `merge-base(base, head)..head`. On a **release PR** (`release/X.Y.Z` → `main`) of a freshly migrated consumer, that span covers the entire pre-devkit history since the last release — commits merged before the commit gate existed and never subject to it. A single non-compliant historical commit (here `9574ee12`, missing the `Refs:` line, merged 4 months pre-migration) permanently blocks the first release train: the commit is immutable shared history, and it is neither a merge commit nor bot-authored, so no built-in exemption applies.

The gate self-heals after the first release lands on `main` (merge-bases move past the old history), so this bites exactly once — at the worst possible moment of a migration.

## Consumer-side workaround (applied)

Hand-patched `ci.yml` (vig-os/sync-issues-action#113, PR vig-os/sync-issues-action#114): advance `BASE_SHA` past the known-bad SHA behind `git merge-base --is-ancestor "$BASE_SHA" "$WAIVED"` — only tightens ranges that already contain the commit; never widens dev-PR ranges.

## Suggested fixes (preference order)

1. Skip commits already reachable from the trunk branch (`origin/dev`) in release-PR validation — they were gated (or grandfathered) on their way into trunk; the release PR should not re-litigate them.
2. A `--waive <sha>[,<sha>]` / waiver-file input on `validate-commit-range` for declarative grandfathering instead of hand-patching a managed workflow.
3. Document the one-time migration hazard + recommended hand-patch in MIGRATION.md.

Related: the codeql.yml hand-patch pattern (#1142) — same "managed file needs a consumer-local deviation" shape.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 03:00 PM_

Fixed via #1153 (merged to dev). validate-commit-range gains `--exclude-reachable` and the scaffolded ci.yml passes `origin/dev` on non-dev PRs, so a first release PR no longer re-lints pre-gate trunk history. Ships with the next devkit release.

