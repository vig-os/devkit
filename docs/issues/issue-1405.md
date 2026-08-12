---
type: issue
state: closed
created: 2026-08-10T13:40:33Z
updated: 2026-08-10T14:15:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1405
comments: 1
labels: refactor, priority:medium, area:workflow, effort:small, semver:minor
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:25.068Z
---

# [Issue 1405]: [refactor: drop the per-train adoption issue from devkit-upgrade.yml](https://github.com/vig-os/devkit/issues/1405)

## Problem

The devkit-upgrade workflow (#1296) creates a per-train adoption issue before committing, because the branch name embeds the issue number and the commit carries `Refs: #N`. In practice the issue is dead weight, same as Renovate PRs which carry no issue:

- On gitflow consumers the PR targets `dev`, where `Closes #N` never auto-closes — every train strands an open issue (live example: vig-os/commit-action#140, still open after PR #141 merged).
- The no-diff cleanup step (#1347) exists solely to garbage-collect issues this workflow itself created.
- Nothing structurally requires the issue: the branch guard explicitly allows `chore/<summary>` without an issue number, `chore` commits are `Refs:`-exempt, and with #1404 the changelog entry links the PR, not the issue.

## Design

In `assets/workspace/.github/workflows/devkit-upgrade.yml`:

- Remove the "Find or create the adoption issue" step and the entire #1347 no-diff cleanup step (the stranded-issue problem disappears structurally).
- Branch: `chore/devkit-<train-suffix>` (guard-legal `chore/<summary>` shape, dots → dashes as today).
- Commit: `chore: adopt devkit X.Y.Z` with no `Refs:` line (chore exemption; hooks still validate in the project shell).
- PR body: drop `Closes #N`; link the devkit release notes instead.
- Token mint: drop `permission-issues: write` (and the issues:write mention in the header docstring).
- Update the header docstring + `docs/DOWNSTREAM_RELEASE.md` where the issue flow is described.

Doctrine: adoption PRs are bot PRs like Renovate's — the PR is the traceable artifact; the changelog entry (#1404) links it.

## Rollout

- Takes effect one train after shipping (the workflow runs from the consumer's base branch).
- One-time migration: manually close the currently-open adoption issues on consumers (e.g. vig-os/commit-action#140).

## Acceptance criteria

- [ ] Issue/cleanup steps removed; branch, commit message, PR body, and token permissions updated
- [ ] `tests/test_workflow_devkit_upgrade.py` updated to assert the new shape
- [ ] Docs + `CHANGELOG.md` Unreleased entry updated

Refs: #1404
---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 02:15 PM_

Shipped to dev via PR #1408 (merge commit 47572fef, auto-merged green 2026-08-10). The devkit-upgrade workflow no longer manages an adoption issue: branch `chore/devkit-<train>`, staging commit without `Refs:`, PR body links the devkit release notes, `issues: write` dropped from the token mint, and the #1347 no-diff cleanup step is deleted. Takes effect on each consumer one train after it adopts the release shipping this (the workflow runs from the consumer's base branch). Remaining one-time migration tracked here: close adoption issues stranded by earlier trains (e.g. vig-os/commit-action#140). Closing manually — dev-targeted PRs don't auto-close.

