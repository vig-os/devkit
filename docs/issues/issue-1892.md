---
type: issue
state: open
created: 2026-10-14T20:18:57Z
updated: 2026-11-03T09:28:29Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1892
comments: 1
labels: feature, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:24:02.935Z
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

---

# [Comment #1]() by [gerchowl]()

_Posted on November 3, 2026 at 09:28 AM_

Field data from a consumer implementation: `exoma-ch/ravmatic` (private, Free org, gitflow) carries this tripwire as `.github/workflows/trunk-guard.yml`, built to almost exactly this spec. Notes for the reusable version:

- **gitflow needs `dev` too.** Make `branch` a list (`main,dev`). In gitflow, `dev` is where stray pushes land.
- **Allow by `sender.type == Bot`, not only `ignore-authors`.** The train pushes as several Apps (commit App, Release App, devkit-upgrade, Renovate). Matching on sender type covers them with no list to maintain. Keep `ignore-authors` for humans.
- **Flag force-pushes and deletions separately.** `github.event.forced` gives a violation even when every new commit is PR-associated. A `delete` trigger filtered to the protected names catches branch deletion.
- **The retry matters.** Verified true negative: a UI merge (#3 there) passed via `commits/SHA/pulls` with `merged_at` and `base.ref` matching. Verified true positive: an empty commit pushed with `--no-verify` failed the run and opened the issue with an @-mention of the pusher.
- Gotcha: `body="$(printf '...:\n\n' ...)"` drops the trailing newlines, so append them after the substitution.

The local half (pre-commit and pre-push gates) is proposed in #1996.

