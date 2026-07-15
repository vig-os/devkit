---
type: issue
state: open
created: 2026-07-15T12:20:03Z
updated: 2026-07-15T12:20:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1115
comments: 0
labels: bug, priority:low, area:ci, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:02.752Z
---

# [Issue 1115]: [prepare-release: dev-side changelog-mirror reconcile is not an ancestor of the release branch — sync-main-to-dev conflicts on the mirror every cycle](https://github.com/vig-os/devkit/issues/1115)

## Summary

Every release cycle, the post-promote `sync-main-to-dev` PR conflicts on exactly one file: the workspace changelog mirror `assets/workspace/.devcontainer/CHANGELOG.md`. The root `CHANGELOG.md` auto-merges cleanly. Observed in 1.2.0 (#1091) and again in 1.2.1 (#1114). The conflict is deterministic and structural, not incidental.

## Root cause (verified on the 1.2.1 cycle)

The merge base between `dev` and `main` at sync time is the **root-only freeze commit** (`849b324a` "chore: freeze changelog for release 1.2.1"), because the release branch is cut from it. So for the **root** changelog, the freeze rewrite is *shared ancestry*: dev makes no further root edits, main's edits (`[1.2.1]` section insertion, date stamp, release-branch amendments) are pure insertions → clean 3-way merge.

The **mirror** is different by design: the #1059 prepare-release extension reconciles it *after* the release branch already exists, as two separate per-branch commits:

- on `dev`: `11ff0e1c` "chore: reconcile workspace changelog mirror after freeze for 1.2.1" — **not** in main's ancestry;
- on `release/1.2.1`: the extension's own mirror sync, further modified by finalize's date stamp and (this cycle) the #1113 amendment via the `sync-manifest` hook.

The mirror's merge base is therefore the *stale pre-freeze* content (populated `## Unreleased` at the top of the file), and both sides rewrote that same region differently → guaranteed overlap conflict. The root's divergence point is after its rewrite; the mirror's is before its rewrite. That asymmetry is the entire mechanism.

This is out of #1059's scope, not a regression: the extension's goal was dev-side root/mirror consistency during the release window (keeping `sync-manifest` green on dev PRs), with the dev reconcile deliberately last so every failure path leaves dev consistent.

## Fix directions

Make the dev-side mirror reconcile an **ancestor of the release branch**, so the mirror gains the same shared-ancestry property as the root:

1. Reorder prepare so the mirror reconcile lands on `dev` before the release branch is cut (requires the extension contract to grow a pre-branch step, or folding the devkit-specific mirror copy into the freeze commit — currently avoided because prepare-release.yml is scaffold-shaped/consumer-generic).
2. Alternatively, have the extension cherry-pick the *identical* reconcile commit to both branches so content and ancestry converge.

Either way the rollback semantics of the `prepare → extension → open-pr` job chain must be preserved (extension failure deletes the partial release branch and restores dev).

**Workaround (status quo):** the conflict is mechanical to resolve — mirror = copy of the resolved root — and the sync workflow already anticipates it (PR title "sync dev with main (conflicts)"). This issue is about removing the recurring manual step, not correctness.

## References

- #1059 (prepare-release extension: root-only freeze + post-branch mirror reconcile)
- #1091 (1.2.0 sync PR, same conflict shape), #1114 (1.2.1 sync PR)
- Evidence commits: `849b324a` (freeze, merge base), `11ff0e1c` (dev-only mirror reconcile)

