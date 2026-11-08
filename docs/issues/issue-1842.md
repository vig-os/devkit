---
type: issue
state: open
created: 2026-10-06T10:43:13Z
updated: 2026-10-08T08:51:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1842
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-09T08:49:29.582Z
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

---

# [Comment #1]() by [c-vigo]()

_Posted on October 8, 2026 at 08:51 AM_

Confirmed on devkit 1.18.0 in a downstream consumer (trunk workflow): the freeze commit on `release/X.Y.Z` left `CHANGELOG.md` ending in `\n\n`, `end-of-file-fixer` failed Lint & Format on the release PR, and `release.yml`'s CI-green gate then refuses the final. Worked around with a one-line PR into the release branch that strips the extra newline.

