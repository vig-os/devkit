---
type: issue
state: open
created: 2026-11-04T04:27:48Z
updated: 2026-11-04T04:27:48Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2025
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:29.548Z
---

# [Issue 2025]: [Consumer seed CHANGELOG on dev carries devkit release entries](https://github.com/vig-os/devkit/issues/2025)

`assets/workspace/CHANGELOG.md` is the seed CHANGELOG that new consumer projects get. On main it is an empty skeleton. On dev it now carries six devkit entries: five #1994 Typst entries and one #1851 promote entry. They were added by feature PRs that edited the seed alongside the root CHANGELOG. A fresh scaffold from dev ships these entries into every new project.

Acceptance:
- Remove the devkit entries from `assets/workspace/CHANGELOG.md`, so it is byte-identical to main's skeleton (or the intended template).
- Add a guard that fails when the seed CHANGELOG contains entries: a test or pre-commit check, plus a note in the changelog rules (CLAUDE.md/CONTRIBUTING: devkit entries go in the root CHANGELOG.md; the `.devcontainer` mirror is generated; the workspace seed is never edited for devkit changes).

Refs: #1994
