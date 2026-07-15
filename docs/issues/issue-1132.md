---
type: issue
state: closed
created: 2026-07-15T16:04:23Z
updated: 2026-07-15T16:21:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1132
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:00.161Z
---

# [Issue 1132]: [[BUG] Promote validate doesn't check PR mergeability — release is undrafted (irreversible) then merge fails, leaving a half-promoted release](https://github.com/vig-os/devkit/issues/1132)

## Summary

`promote-release.yml`'s `validate` job verifies the release PR exists, is non-draft, is approved, and has green CI — but it **never checks whether the PR is actually mergeable** (`mergeable` / `mergeStateStatus`). So a PR that is approved + CI-green but **BEHIND** (or `BLOCKED`/`DIRTY`) passes validation, the `promote` job then **undrafts the GitHub Release (irreversible)**, and only afterwards does the `merge` job fail. The result is a **half-promoted release**: a published GitHub Release whose PR never merged to `main`.

## Why it matters

The promote sequence is `validate → promote (undraft) → merge → cleanup`, and `promote` is irreversible (publishing locks the tag under GitHub immutable releases). `validate` exists precisely to guarantee the whole sequence can complete before starting it. Mergeability is part of "can this promote complete", so it belongs in `validate` — otherwise a merge-blocked PR is only discovered *after* the release is already public, and the run cannot be re-run to recover (validate then rejects the now-published release as non-draft, so completing the merge has to be done out-of-band).

## Observed

vig-os/commit-action 0.3.0 promote — run https://github.com/vig-os/commit-action/actions/runs/29430147324:
- `Validate promote prerequisites` ✓
- `Publish GitHub Release` ✓ (undraft — release now public)
- `Merge release PR to main` ✗ — `Pull request #78 is not mergeable: the head branch is not up to date with the base branch.`

`release/0.3.0` was BEHIND `main` by 5 CI-only commits merged after the release branch was cut. `main` enforces "require branches up to date before merging", and the merge step uses plain `gh pr merge --merge` (no `--admin`/`--auto`), so it cannot override it. Net state: v0.3.0 published, PR #78 still open.

## Root cause

In `validate → Find and verify release PR`, the `gh pr list` query requests `number,isDraft,reviewDecision,statusCheckRollup` and asserts on those, but omits `mergeable` and `mergeStateStatus`.

## Proposed fix

In `validate`, also fetch and assert mergeability before the promote job runs — fail fast unless the PR is in a mergeable state, e.g. `mergeStateStatus == CLEAN` (or at minimum reject `BEHIND`/`BLOCKED`/`DIRTY`/`UNKNOWN`, re-querying on `UNKNOWN` since GitHub computes it asynchronously). Keeps the invariant: never start the irreversible publish unless the merge can succeed.

## Secondary considerations (not required for the fix)

- **TOCTOU:** `main` can advance between `validate` and `merge`. The validate check closes the common case (branch already behind at dispatch); the `merge` step could additionally handle a late `BEHIND` — either `gh pr merge --auto` (queue until requirements met) or an explicit "update branch + re-verify" — rather than failing after publish. Worth deciding as part of this, but the primary ask is the fail-fast validate gate.
- Whether the merge step should update the release branch itself when BEHIND is a related design choice; the minimal fix is validate-time detection.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 04:21 PM_

Fixed in #1133 (merged to \`dev\`).

The scaffold \`promote-release.yml\` \`validate\` job now fetches
\`mergeable\`/\`mergeStateStatus\` and fails fast unless the release PR is
mergeable — accepting \`CLEAN\`/\`HAS_HOOKS\`/\`UNSTABLE\`, rejecting
\`BEHIND\`/\`BLOCKED\`/\`DIRTY\`, and re-querying while GitHub still reports
\`UNKNOWN\` (mergeability is computed asynchronously). This restores the
invariant that the irreversible publish never starts unless the merge can
complete.

Scope is the downstream scaffold template
(\`assets/workspace/.github/workflows/promote-release.yml\`) — the primary
fail-fast \`validate\` gate. The secondary considerations (TOCTOU between
validate/merge; \`gh pr merge --auto\` or branch-update in the merge step) were
intentionally left out of this minimal fix.

Ships to consumers on the next devkit release. commit-action 0.3.0's
already-published release still needs an out-of-band manual merge of its release
PR to recover.

Closed manually: \`Closes #N\` only auto-closes on merge to the default branch
(\`main\`), not \`dev\`.

