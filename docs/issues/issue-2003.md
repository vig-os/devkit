---
type: issue
state: open
created: 2026-11-03T10:02:57Z
updated: 2026-11-03T10:02:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2003
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:58.496Z
---

# [Issue 2003]: [abandon-release leaves dev's frozen [X.Y.Z] - TBD CHANGELOG section behind](https://github.com/vig-os/devkit/issues/2003)

`prepare-release` freezes dev's `## Unreleased` into `## [X.Y.Z] - TBD` and commits that to dev. `abandon-release.yml` deletes the draft release, the tag, the PR and the branch, but it does not undo that freeze on dev.

After 1.19.0 was abandoned (2026-10-29), dev still carries `## [1.19.0] - TBD` (CHANGELOG.md line ~143) below a separately growing `## Unreleased`. Consequences:
- The next `prepare-release 1.19.0` meets a pre-existing `[1.19.0]` section.
- Entries are split across two sections.
- Post-hotfix syncs have to work around the stale section (seen in #1991).

Acceptance:
- `abandon-release` (gitflow, regular train) folds dev's `## [X.Y.Z] - TBD` back into `## Unreleased`, merging categories. It does this idempotently, through the same API-commit path that prepare-release uses, with the workspace mirror re-synced.
- A one-off fix folds dev's current stale `[1.19.0] - TBD` back into Unreleased.
- Tests, plus a RELEASE_CYCLE update (abandon section).

Refs: #1985
