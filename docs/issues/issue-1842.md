---
type: issue
state: open
created: 2026-10-06T10:43:13Z
updated: 2026-10-06T10:43:13Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1842
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-07T08:29:21.359Z
---

# [Issue 1842]: [prepare-release: changelog freeze leaves a trailing blank line (end-of-file-fixer fails the release PR)](https://github.com/vig-os/devkit/issues/1842)

## What happens

`prepare-release.yml`'s changelog freeze (`prepare-changelog`) drops the empty trailing sections of the frozen block (here `### Removed` and `### Security` were empty) but leaves the blank line that preceded them. The file then ends in `\n\n`.

The scaffolded `end-of-file-fixer` hook rejects that, so **Lint & Format fails on the draft release PR**, and `release.yml` final refuses to run (`PR #N has failed CI checks`) until someone pushes a bugfix to `release/X.Y.Z`.

## Repro

1. A consumer CHANGELOG whose `## Unreleased` has content under `Added`/`Changed`/`Fixed` and empty `### Removed` + `### Security` as the last headings (the seeded order).
2. `gh workflow run prepare-release.yml -f version=0.1.0`.
3. `git show origin/release/0.1.0:CHANGELOG.md | tail -c 4 | od -c` → `)  )  \n  \n`.

Seen on devkit 1.18.x, trunk workflow, solo profile; first release of a repo.

## Expected

The frozen file ends with exactly one newline (strip trailing blank lines after removing empty sections), so the release PR's CI is green straight out of `prepare-release`.

