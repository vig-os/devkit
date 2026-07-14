---
type: issue
state: closed
created: 2026-07-14T11:20:44Z
updated: 2026-07-14T11:37:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1052
comments: 1
labels: chore, priority:medium, area:ci, effort:small, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:27.949Z
---

# [Issue 1052]: [chore(ci): resolve check-pr-agent-fingerprints dead code — wire into commit-checks](https://github.com/vig-os/devkit/issues/1052)

## Problem

Surfaced while scaffolding `check-agent-identity` (#1031, PR #1032). The `check-pr-agent-fingerprints` entry point exists (`packages/vig-utils/pyproject.toml`) but is referenced by **no** workflow — devkit's or the scaffold's. A guard that nothing calls is not a guard; this is the same documented-but-uncalled false-guarantee shape #1019/#1031 fixed elsewhere.

Coverage analysis (from the #1032 investigation): after #1026 the `commit-checks` job already guards the **PR title** via `validate-commit-range --title`; this entry point's only unique coverage is the **PR body** (reads `PR_TITLE`/`PR_BODY` from env, greps against `.github/agent-blocklist.toml`).

## Decision

**Wire it into the `commit-checks` job** (devkit's `ci.yml` and the scaffold's) as a cheap defense-in-depth step passing `PR_BODY` — the blocklist and helper already exist, and PR-body text is visible in the UI/notifications even though it never enters git history. Dropping it remains the fallback if wiring surfaces problems.

## Acceptance criteria

- [ ] `commit-checks` (both ci.yml copies) runs `check-pr-agent-fingerprints` with the PR title+body on pull_request events
- [ ] A PR whose body matches the agent blocklist fails the job; a clean PR passes
- [ ] No longer dead code: `grep -r check-pr-agent-fingerprints .github assets/workspace/.github` has hits

Refs: #163, #1031, #1026
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 11:37 AM_

Implemented in #1058 (merged to dev): check-pr-agent-fingerprints now runs in commit-checks (both ci.yml copies), PR title+body passed injection-safe via env. The #163 pipeline has no remaining uncalled guards.

