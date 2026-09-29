---
type: issue
state: open
created: 2026-09-28T12:10:31Z
updated: 2026-09-28T12:10:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1747
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:54.860Z
---

# [Issue 1747]: [[FEATURE] Changelog synthesis recipe for prepare-release-extension.yml (git-cliff)](https://github.com/vig-os/devkit/issues/1747)

### Description

Ship a `prepare-release-extension.yml` **recipe** (docs + optional seed snippet) that synthesizes the `## [X.Y.Z] - TBD` changelog section from conventional commits with `git-cliff`, for consumers that do not hand-author `## Unreleased`.

Split out of #1746 as a follow-up (its "Follow-ups (out of scope for this cut)" section).

### Problem Statement

The train reads a hand-authored root `## Unreleased` section. Rust repos coming from release-plz (tessera, per vig-os/tessera#441 blocker 3) are used to changelogs generated from commits. Without a recipe, every such adopter either changes the whole team's habit at once or invents a generator step.

### Proposed Solution

- Document a `prepare-release-extension.yml` job that runs `git-cliff` over the commits since the last stable tag and commits the result onto the fresh `release/X.Y.Z` branch (COMMIT_APP token, honours `dry_run`), before the PR opens.
- Use `git-cliff`, **not** release-plz: release-plz has no changelog-only mode and wants to own version, tag and PR itself, which collides with the train.
- Opt-in only; the hand-authored model stays the default.

### Alternatives Considered

- release-plz `--changelog-only`: that mode does not exist.
- Folding this into #1746: rejected on reviewer advice (language-neutral train PR stays free of changelog opinions).

### Additional Context

- Parent: #1746. Related: #1496 (Rust pack track), vig-os/tessera#441.

### Impact

Additive, opt-in. No change for existing consumers.

### Changelog Category

Added

