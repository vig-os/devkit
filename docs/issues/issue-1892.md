---
type: issue
state: open
created: 2026-10-14T20:18:57Z
updated: 2026-10-14T20:18:57Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1892
comments: 0
labels: feature, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:43.324Z
---

# [Issue 1892]: [[FEATURE] Soft main guard: reusable workflow that alerts on commits reaching main without a merged PR](https://github.com/vig-os/devkit/issues/1892)

## Description

A reusable workflow (`workflow_call`) that raises an **alert** when a commit lands on a protected branch (default: `main`) without being part of a merged pull request. Alert only: it opens or updates one tracking issue; it never reverts or force-pushes.

## Problem Statement

Branch protection and rulesets on private repos need GitHub Team. Repos on the Free plan (e.g. `vig-os`, `MorePET`, `exoma-ch` private repos) cannot stop a direct push to `main`, and nothing tells the team it happened. A cheap, after-the-fact tripwire gives them most of the audit value: someone sees "commit X reached main without a PR" the same hour.

## Proposed Solution

- `.github/workflows/main-guard.yml`, `on: workflow_call`, inputs: `branch` (default: the repo default branch), `label` (default `main-guard`), `ignore-authors` (comma-separated logins, e.g. release bots), `runner` (JSON label list, default hosted).
- For each commit in `github.event.before..after` (compare API; head only for a new branch or a non-ancestor force-push), call `gh api repos/R/commits/SHA/pulls` and keep PRs with `merged_at != null` and `base.ref == branch`. The endpoint lags right after a merge, so retry a few times before declaring a commit unassociated.
- Unassociated commits: open one issue (label `main-guard`), or comment on the already-open one. Nothing else is written.
- Permissions needed in the caller: `contents: read`, `issues: write`, `pull-requests: read`.
- Documented in `docs/MAIN_GUARD.md` with a caller snippet; behaviour pinned by `tests/test_main_guard.py` (actionlint-clean workflow shape + the real `run:` script executed against a fake `gh` and fixtures).

## Alternatives Considered

- Auto-revert: rejected; a wrong revert on `main` is worse than the problem, and bots/hotfixes legitimately push.
- GitHub rulesets / merge queue: need Team / Enterprise Cloud on private repos; this is the Free-plan fallback and stays useful as a second line on Team repos.

## Impact

New file only; no change to the release train or the scaffold. Consumers opt in by adding the caller snippet.

