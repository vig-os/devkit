---
type: issue
state: open
created: 2026-11-11T12:15:38Z
updated: 2026-11-11T12:15:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2071
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-12T09:37:23.639Z
---

# [Issue 2071]: [prepare-changelog: no structure-only validate mode (validate rejects an empty Unreleased, so it cannot gate commits on release branches)](https://github.com/vig-os/devkit/issues/2071)

`prepare-changelog validate` checks two things at once: structure (loose bullets, a repeated standard `### ` heading) and content (`## Unreleased` must have entries). A consumer that wants to gate every commit on structure alone cannot use it: on a release branch the freeze leaves Unreleased empty by design, and `validate` exits 1 with `Unreleased section is empty (no changes to release)`.

Repro: a CHANGELOG with an empty `## Unreleased` and a populated `## [0.1.0] - TBD` section; `prepare-changelog validate CHANGELOG.md` exits 1.

Request: a structure-only mode (for example `validate --structure-only`) that runs the existing duplicate-heading and loose-bullet checks over `## Unreleased` and every `## [X.Y.Z]` section, accepts an empty Unreleased, and exits 0/1 on structure alone. The checks are already shared helpers; the missing piece is a way to skip the content requirement. Today a consumer has to reimplement the duplicate-heading check.
