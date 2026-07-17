---
type: issue
state: closed
created: 2026-07-16T14:38:52Z
updated: 2026-07-16T15:20:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1152
comments: 1
labels: docs, priority:medium, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:01.918Z
---

# [Issue 1152]: [First-release manual promote cannot move floating tags: Tag ruleset is Release-App-exclusive by design](https://github.com/vig-os/devkit/issues/1152)

## Context

Companion to the promote-release registration issue (same first-release train on vig-os/sync-issues-action). `DEVKIT_TAG_PREFIX=v`, `DEVKIT_FLOATING_TAGS=major,minor`.

## Problem

The imported Tag protection ruleset bypasses only the Release App (Integration) — correct for steady state, where `promote-release.yml` moves `vX`/`vX.Y` with the app token. But on a **first release** the promote workflow is not dispatchable (see companion issue), and no human — not even a repo/org admin — can create or move the floating tags: `gh api -X PATCH .../git/refs/tags/v0` → `422 Cannot update this protected ref`. The consumer ends the train with the release published but `vX` pointing at the previous release and `vX.Y` missing — silently breaking the advertised `uses: owner/repo@vX` pin for the new version.

## Suggested fix

Document the one-off bootstrap in MIGRATION.md: temporarily add a `RepositoryRole: admin` (actor_id 5) bypass to the tag ruleset, create/move the floating tags at the peeled release commit (same `move_tag` semantics as promote-release.yml), delete any orphan rc tags, then **revert the ruleset**. Alternatively ship a small consumer-ownable dispatch workflow that performs only the floating-tag move with the Release App token, registered from day one of the migration.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 03:20 PM_

Documented via #1156 (merged to dev). docs/MIGRATION.md gains a "First-release floating tags" subsection: temporarily grant a RepositoryRole admin bypass on the Tag ruleset, move vX / vX.Y to the peeled release commit (same move_tag semantics as promote-release.yml), then revert the ruleset. Ships with the next devkit release.

