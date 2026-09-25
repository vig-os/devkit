---
type: issue
state: open
created: 2026-09-24T17:23:07Z
updated: 2026-09-24T17:23:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1679
comments: 0
labels: bug, priority:high, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-25T07:32:56.529Z
---

# [Issue 1679]: [prepare-hotfix: freeze main's Unreleased instead of refusing](https://github.com/vig-os/devkit/issues/1679)

## Problem Statement

`prepare-hotfix.yml:163` refuses to start when `main`'s `## Unreleased` section has content:

```
ERROR: main's ## Unreleased section has content; a hotfix seeds an EMPTY section
```

That rests on #590's invariant — *main's Unreleased is empty by construction, because every release freezes it on `dev` and `main` only ever receives release branches*. #1676 supersedes that invariant: `main` may now carry changes that have landed but are not yet shipped, and its `## Unreleased` describes them.

Under the new model the refusal is wrong, and it is the **only** mechanical blocker to `main` carrying unshipped work. Leaving it would mean the hotfix lane — the lane that exists for urgent security incidents — silently refuses whenever the release-neutral lane has been used.

## Proposed Solution

A hotfix cuts from `main`'s head, so it **ships** whatever is on `main`, including those carried changes. Their changelog entries therefore belong in the hotfix's own version section.

Replace the refusal with a branch on content:

- `main`'s Unreleased **has content** → `prepare-changelog prepare X.Y.Z` on the release branch, freezing the carried entries into `## [X.Y.Z] - TBD` (plus a fresh empty Unreleased). This is the same call `prepare-release` already makes on `dev`.
- `main`'s Unreleased is **empty** → `prepare-changelog seed X.Y.Z` exactly as today.

Main's `## Unreleased` then self-clears when the release branch merges back, so the invariant re-establishes itself after every hotfix.

Both commands already exist (`prepare-changelog {prepare,seed,...}`), so this is a branch in the workflow, not new machinery.

Also update:

- The `CHANGELOG flow` header comment in `prepare-hotfix.yml` (lines 26-30), which documents the old invariant.
- The workflow-shape tests covering the hotfix lane.
- The #590 reference in `docs/RELEASE_CYCLE.md`'s hotfix section.

### Explicitly decided: the publish-time gate does NOT change

`release.yml`'s `prepare-changelog validate --version` still refuses to publish a version whose section is empty. **No empty sections at release time; empty is acceptable at `prepare-hotfix` time.**

This does mean carried entries can satisfy that gate without the hotfix's own fix being described. Accepted deliberately — no compensating check.

## Alternatives Considered

- **Keep refusing, and require `main`'s Unreleased to be drained before a hotfix.** Rejected: it makes the release-neutral lane and the hotfix lane mutually exclusive, which is the opposite of what #1676 is for.
- **Freeze on `main` rather than the release branch.** Rejected: `prepare-hotfix` deliberately never writes to `main` (rollback is then just "delete the branch"), and that simplicity is worth keeping.

## Impact

Breaking change: no. Behaviour changes only in the case that is currently a hard error.

**Scaffold split to expect:** `prepare-hotfix.yml` also ships in `assets/workspace/.github/workflows/`. Devkit's **own** copy is release-neutral and can ride the #1676 lane; the **scaffold** copy is a published asset and still needs a release. Land them as separate commits.

## Changelog Category

Fixed

