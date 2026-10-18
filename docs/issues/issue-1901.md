---
type: issue
state: open
created: 2026-10-17T23:50:18Z
updated: 2026-10-17T23:50:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1901
comments: 0
labels: bug, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-18T07:08:58.038Z
---

# [Issue 1901]: [prepare-release changelog freeze leaves a blank line at EOF when it drops an empty trailing section (end-of-file-fixer then fails on the release branch)](https://github.com/vig-os/devkit/issues/1901)

Seen on vig-os/vigil prepare-release 0.1.0 (run 38946591963), freeze commit vig-os/vigil@322d80d. Before the freeze, `CHANGELOG.md` ended with an empty `### Security` heading plus `\n`. The freeze removed the empty heading but left the preceding blank line, so the file ends in `\n\n`. The release branch's CI then fails Lint & Format (`end-of-file-fixer ... Failed — Fixing CHANGELOG.md`, run 38947429102), and the final `release.yml` refuses with '#155 has failed CI checks'. The commit also lands on dev, which breaks precommit for every PR touching the CHANGELOG. Expected: the freeze normalises the file to end with exactly one `\n` (or trims trailing blank lines after dropping empty sections); add a fixture with an empty trailing section.
