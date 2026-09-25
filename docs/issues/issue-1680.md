---
type: issue
state: open
created: 2026-09-24T17:23:08Z
updated: 2026-09-24T17:23:08Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1680
comments: 0
labels: feature, priority:medium, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-25T07:32:56.112Z
---

# [Issue 1680]: [prepare-release: refuse to cut a release while dev is behind main](https://github.com/vig-os/devkit/issues/1680)

## Problem Statement

`prepare-release` freezes **`dev`'s** `## Unreleased` into the new version section. Under #1676, `main` may carry changes — and changelog entries — that have landed but are not yet shipped.

`sync-main-to-dev.yml` propagates those to `dev` automatically (it triggers on `push: [main]`), so in the normal case `dev` already has them by the time a release is cut. But nothing *enforces* that ordering. If a release is prepared while that sync PR is still open, the carried entries are silently left out of the frozen section, and the release ships without describing changes it actually contains.

## Proposed Solution

Add a validate-job precondition to `prepare-release.yml`: refuse when `dev` is behind `main`.

```bash
BEHIND=$(git rev-list --count origin/main ^origin/dev)
[ "$BEHIND" = "0" ] || refuse
```

This is the same check `sync-main-to-dev.yml` already performs to decide whether to open its PR, so the two agree by construction rather than by coincidence. The remedy is always the same and easy to state in the error: merge the open `chore/sync-main-to-dev-*` PR, then re-dispatch.

Worth having regardless of #1676 — cutting a release from a `dev` that is behind `main` has never been intentional.

## Alternatives Considered

- **Warn instead of refuse.** Weaker: the failure mode is a silently incomplete changelog on a published release, which is not noticed until someone goes looking. Prefer refusing, since the fix is one PR merge away. Open to reversing this if it proves obstructive in practice.
- **Have `prepare-release` merge `main` into `dev` itself.** Rejected: it would make the release lane a writer of `dev` outside the freeze commit, and `sync-main-to-dev` already owns that job.

## Impact

Breaking change: no. Adds a precondition that should already hold in every intended workflow.

**Scaffold split to expect:** `prepare-release.yml` also ships in `assets/workspace/.github/workflows/`. Devkit's own copy is release-neutral and can ride the #1676 lane; the scaffold copy is a published asset and needs a release. Land them as separate commits.

## Changelog Category

Added

