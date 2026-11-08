---
type: issue
state: open
created: 2026-11-06T10:22:58Z
updated: 2026-11-06T10:22:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2058
comments: 0
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T10:28:39.022Z
---

# [Issue 2058]: [devkit-upgrade PR body should carry the version range's migration notes](https://github.com/vig-os/devkit/issues/2058)

Found in the 1.19.0-rc5 live consumer check. The adoption PR body opened by `devkit-upgrade.yml` is a fixed three-line template: an "Automated devkit upgrade to X via install.sh --force" line, a release-notes link, and a flake-bump note. It names none of the migration steps for the version range being crossed.

Example: 1.18.x → 1.19.0 deprecates the `DEVKIT_CI_RESOLVE_RUNNER` variable in favour of `CI_RUNNER_SMALL`, and introduces `DEVKIT_CI_CONTAINER_RUNNERS` for container mode (#2045). Both are documented in docs/MIGRATION.md, but a reviewer of the adoption PR never sees them. The manual steps (delete the legacy variable after merge; opt in to container runners) depend on someone reading MIGRATION.md by hand.

**Proposal:** structure MIGRATION.md per version (it may already be close), and have the upgrade job include in the PR body the entries for every version in `(from, to]`. Also list the consumer's own state that matters, e.g. "the repo variable DEVKIT_CI_RESOLVE_RUNNER is set and deprecated: delete it after merge".

**Acceptance:** an upgrade PR crossing a version that has migration notes lists them, plus any deprecated settings detected in the repo; a test covers both.
