---
type: issue
state: closed
created: 2026-07-15T17:08:52Z
updated: 2026-07-15T17:30:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1136
comments: 1
labels: area:workflow, effort:medium, semver:patch, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:03:59.752Z
---

# [Issue 1136]: [Workflow templates grant vestigial job-level write permissions to GITHUB_TOKEN](https://github.com/vig-os/devkit/issues/1136)

## Summary

An OpenSSF Scorecard TokenPermissions audit of a consumer repo (`vig-os/commit-action`, 17 open code-scanning alerts) traced every job-level `contents: write` / `actions: write` grant in the rendered devkit workflows to the token that actually performs the write. Result: **16 of 17 grants are vestigial** — every git push, tag push, `gh release`, `gh pr`, `gh api` mutation and `gh workflow run` rides a COMMIT_APP / RELEASE_APP installation token, not the job's `GITHUB_TOKEN`. The rendered permission blocks are byte-identical to the templates in `assets/workspace/.github/workflows/`, so the fix belongs here and propagates to all consumers on upgrade.

All bare `git push` sites (4 total) sit after an `actions/checkout` that injects an App `token:`, so persist-credentials pushes with the App token:
- `release-publish.yml` publish → tag push after `token: steps.auth.outputs.token` (RELEASE_APP fallback)
- `sync-main-to-dev.yml` sync (×2) → after `token:` COMMIT_APP checkout
- `release.yml` rollback → `git push --force-with-lease` guarded by the same `pre_finalize_sha != ''` condition as its COMMIT_APP checkout

## Safe reductions (write → read on GITHUB_TOKEN)

| Template (assets/workspace/.github/workflows/) | Job | Grant |
|---|---|---|
| prepare-release.yml | prepare | contents |
| prepare-release.yml | rollback | contents |
| promote-release.yml | promote | contents |
| promote-release.yml | merge | contents |
| promote-release.yml | cleanup | contents |
| promote-release.yml | floating-tags | contents |
| release.yml | core (caller block) | actions + contents |
| release.yml | publish (caller block) | contents |
| release.yml | rollback | contents |
| release-core.yml | finalize | actions + contents |
| release-publish.yml | publish | contents |
| sync-issues.yml | sync | contents (KEEP `actions: write` — see below) |
| sync-main-to-dev.yml | sync | contents |

Caller/callee coupling: `release.yml` `core`/`publish` wrap `release-core.yml`/`release-publish.yml` as reusable workflows — reduce both sides in the same change (lowering only one leaves either an over-granting caller or an over-stating callee).

Optional same-justification extras (App-token-driven, not Scorecard-flagged): `prepare-release.yml` open-pr `pull-requests: write`; `promote-release.yml` merge `pull-requests: write`; `release.yml` rollback `issues: write`; `sync-main-to-dev.yml` sync `pull-requests: write` + `issues: write`.

## Two grants that need care

1. **`promote-release.yml` `validate` — NOT a blind reduction.** Its *Verify draft GitHub Release exists* step lists releases with `GH_TOKEN: github.token` and matches a **draft**; GitHub only returns draft releases to tokens with push (`contents: write`) access, so reducing the job to `read` as-is would hide the draft and fail every promotion. Fix: point that step's `GH_TOKEN` at the RELEASE_APP token the job already generates for its PR-check step, then reduce the job to `contents: read`.
2. **`sync-issues.yml` `sync` `actions: write` — REQUIRED, keep.** The *Delete old cache* step calls `gh api .../actions/caches/{id} -X DELETE` with `GH_TOKEN: github.token`. (Could be dropped later by moving that step to an App token with Actions write, but that is a separate behavioral change.)

## Verification notes

- The equivalent top-level fix was already validated downstream: vig-os/commit-action#94 / vig-os/commit-action#95 moved the two repo-local smoke workflows to `permissions: {}` + job-level write; E2E and published-tag smokes pass.
- Template top-level blocks are already read-only across `assets/workspace` — this issue is job-level only.
- Suggested validation for the template change: render into a consumer and run a full rc release cycle (prepare → release → publish → promote → sync), since the affected jobs are exactly the release pipeline.

## Impact

Closes the bulk of consumers' Scorecard TokenPermissions findings at the source and shrinks the blast radius of any compromised step to a read-only `GITHUB_TOKEN` (App tokens remain scoped and short-lived).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 05:29 PM_

Fixed on dev via #1137 (merge commit 51138424). Ships in the next release (1.3.0).

