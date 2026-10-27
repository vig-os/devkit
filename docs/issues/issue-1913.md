---
type: issue
state: open
created: 2026-10-26T18:12:03Z
updated: 2026-10-26T18:12:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1913
comments: 0
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-27T07:38:05.632Z
---

# [Issue 1913]: [[BUG] SECURITY.md claims dependency review blocks PRs, false for private consumer repos](https://github.com/vig-os/devkit/issues/1913)

Follow-up to #1910 / PR #1911.

## Problem
`assets/workspace/SECURITY.md` states "Dependency review blocks pull requests that introduce vulnerable dependencies", but `ci.yml` only runs dependency review for public repos (`!github.event.repository.private`). For private consumers (e.g. `nerdmachines/inox`, which reported #1910) the claim is false: same bug class as #1910.

## Expected
Render or word that line so it is only asserted where dependency review actually runs (public repos), with a test covering repo visibility.

Refs: #1910
