---
type: issue
state: closed
created: 2026-07-13T12:24:25Z
updated: 2026-07-13T16:17:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1016
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T04:57:29.069Z
---

# [Issue 1016]: [fix(ci): scaffolded workflow_call workflows do not declare inherited secrets](https://github.com/vig-os/devkit/issues/1016)

Found during 1.1.0-rc1 validation (PR #1014).

`assets/workspace/.github/workflows/release-publish.yml` and `release-core.yml`
are `workflow_call` workflows. They reference `GHCR_PULL_TOKEN`,
`RELEASE_APP_CLIENT_ID`, `RELEASE_APP_PRIVATE_KEY` (and, in `release-core.yml`,
`COMMIT_APP_CLIENT_ID` / `COMMIT_APP_PRIVATE_KEY`) but declare only `token:` in
their `workflow_call: secrets:` block.

In a `workflow_call` workflow actionlint knows the declared secrets set, so every
undeclared reference is reported as `property "..." is not defined`. Consumers
scaffolded from the workspace assets therefore get a dirty `actionlint` run out
of the box. The devkit s own copies lint clean.

**Expected:** declare the inherited secrets in the `workflow_call: secrets:`
block of both files so a scaffolded consumer lints clean.

**Not in scope:** `promote-release.yml`, `release.yml`, `sync-issues.yml`,
`sync-main-to-dev.yml` are `workflow_dispatch`/`push`/`schedule` triggered, where
secrets are ambient and need no declaration.

Refs: #988
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 04:17 PM_

Fixed by #1018 (commit `cf9f473e` — `fix(ci): declare inherited secrets in scaffolded workflow_call workflows`), released in [1.1.0](https://github.com/vig-os/devkit/releases/tag/1.1.0).

`release-publish.yml` and `release-core.yml` now declare their inherited secrets in the `workflow_call: secrets:` block, so a scaffolded consumer gets a clean `actionlint` run out of the box. Covered by the RED test in `9ac584c2`.

