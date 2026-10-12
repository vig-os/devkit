---
type: issue
state: closed
created: 2026-10-11T15:25:43Z
updated: 2026-10-12T00:37:24Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1863
comments: 1
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:44.534Z
---

# [Issue 1863]: [Release-train workflows ignore DEVKIT_CI_RUNNER: prepare/release/promote/sync-main-to-dev stay on hosted ubuntu-26.04](https://github.com/vig-os/devkit/issues/1863)

`DEVKIT_CI_RUNNER` / `DEVKIT_CI_RESOLVE_RUNNER` (#1173, #1796) route ci.yml and sync-issues onto self-hosted runners. But `prepare-release.yml`, `release.yml`, `release-core.yml`, `release-publish.yml`, `promote-release.yml`, `sync-main-to-dev.yml` and the `*-extension` workflows hard-code `runs-on: ubuntu-26.04`. A consumer whose hosted Actions are unavailable (billing or spending limit, as gerchowl/claude-config since 2026-10-10) can merge PRs on self-hosted runners but can't cut a release.

Expected: the same runner-json routing for the release train, defaulting to hosted. Related: #1860, #1861.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 12, 2026 at 12:37 AM_

Fixed in #1869 (merged into dev): the release train routes runs-on through DEVKIT_CI_RUNNER and DEVKIT_CI_RESOLVE_RUNNER, defaulting to hosted. Seeded extension hooks use the repo variable, and no new input is passed to consumer-owned workflows, so existing consumers' copies keep working (a compatibility test guards it).

