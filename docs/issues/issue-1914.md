---
type: issue
state: open
created: 2026-10-26T18:12:05Z
updated: 2026-10-26T18:12:05Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1914
comments: 0
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-27T07:38:05.252Z
---

# [Issue 1914]: [[BUG] COMMIT_MESSAGE_STANDARD approved-types table ignores DEVKIT_COMMIT_TYPES](https://github.com/vig-os/devkit/issues/1914)

Follow-up to #1910 / PR #1911.

## Problem
With custom types (e.g. `DEVKIT_COMMIT_TYPES=feat,fix,chore,record`), the rendered `docs/COMMIT_MESSAGE_STANDARD.md` Exemptions section lists `record`, but the approved-types table still shows the stock 11 types. Same bug class as #1910 (managed doc false for the consumer's manifest).

## Expected
Render the types table from the resolved `DEVKIT_COMMIT_TYPES` (descriptions for custom types need a defined fallback), with tests.

Refs: #1910
