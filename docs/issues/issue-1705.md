---
type: issue
state: closed
created: 2026-09-25T09:29:10Z
updated: 2026-09-25T15:07:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1705
comments: 2
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:42.234Z
---

# [Issue 1705]: [[BUG] Release-neutral guard leaves a stale positive verdict standing after a gate failure or unlabel](https://github.com/vig-os/devkit/issues/1705)

### Description

Gate 6 of `.github/workflows/release-neutral-guard.yml` (the verdict comment) runs under `if: env.ACTIVE == 'true'` with no `always()`. When an earlier gate fails, or when the `release-neutral` label is removed, gate 6 does not run, so the PR's last **positive** verdict comment stays standing as the only verdict on the PR. #1698 made that comment sticky (one marker-based comment, edited in place), which turns "the stale verdict is buried by newer comments" into "the stale verdict is the permanent, single verdict".

A reviewer reading the PR sees "This change is release-neutral" after a gate-2 failure or after the label was pulled.

### Steps to Reproduce

1. Open a lane PR, let the guard pass (verdict comment posted)
2. Push a commit that moves `devShells.default`'s drvPath (gate 2 fails) or remove the label
3. The verdict comment still says release-neutral

### Expected Behavior

Gate 6 runs whenever a previous verdict exists: on a gate failure it rewrites the sticky comment with the refusal and the failing gate; on deactivation it rewrites it as "lane inactive since <sha>", or deletes it.

### Actual Behavior

The positive verdict from the last green run stands.

### Environment

- **OS**: n/a
- **Container Runtime**: n/a
- **Image Version/Tag**: n/a
- **Architecture**: n/a

### Additional Context

Noted in the #1698 review. Shape rule 1 (the job never carries an `if:`, so it always reports a conclusion) is unaffected; this is step-level.

### Possible Solution

`if: always() && (env.ACTIVE == 'true' || env.LABELLED == 'true')` on gate 6, with the verdict body branching on `steps.<gate>.outcome`; on the unlabeled path, rewrite the sticky comment to an "inactive" stub so it can never be read as a pass.

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: confirmed; the proposed `if:` needs a third discriminator

Map of the current workflow: `unlabeled` already triggers it (no trigger change needed); `ACTIVE` = label present ∧ (not a label event ∨ the event's label is `release-neutral`); `LABELLED` = label present; every step after "Report scope" is gated `if: env.ACTIVE == 'true'`; **no step carries an `id:`**, so `steps.<id>.outcome` branching needs ids added.

- **(a) gate failure on a later push:** the implicit `success()` skips the vulnix extra and gate 6; the job is red, but the guard is not a required check on `main` (the ruleset requires only `Test Summary` and the two CodeQL contexts), so nothing blocks the merge and the stale green verdict is the only verdict text. Real, not cosmetic.
- **(b) label removed:** on the `unlabeled` payload `pull_request.labels` no longer contains the label, so `ACTIVE` **and** `LABELLED` are both false. The proposed `always() && (env.ACTIVE == 'true' || env.LABELLED == 'true')` therefore stays false and the stale verdict survives — the exact half the issue targets. A third env is needed: `DEACTIVATED: ${{ github.event.action == 'unlabeled' && github.event.label.name == 'release-neutral' }}`.
- Use `!cancelled()`, not `always()`: a run cancelled by a superseding head must not overwrite the sticky comment with a bogus refusal (write it as `if: ${{ !cancelled() && … }}`, `!` is a YAML tag otherwise).
- Tree-state trap: on a `vulnix-gate` failure the worktree is still on the base ref (the `git checkout -q -` comes after the failing step), so gate 6's `git diff origin/$BASE_REF...HEAD` would be empty; the refusal branch must `git checkout -q "$GITHUB_SHA"` first or skip the file list.
- Deactivation path must be PATCH-or-nothing (never create), so a label added-then-removed PR gets no noise; the failure path may create.

**Plan:** add `id:`s to the gate steps; gate 6 `if: ${{ !cancelled() && (env.ACTIVE == 'true' || env.DEACTIVATED == 'true') }}` with the body branching on outcomes (all success → verdict; any failure → refusal naming the first failing gate; deactivated → "lane inactive since <sha>" stub); red test in `tests/test_workflow_release_neutral.py` asserting the `if` contains `cancelled()`, `env.ACTIVE` and a deactivation clause, that the gate steps carry ids and the body references `.outcome`; changelog `Fixed`; update the gate 6 row in `docs/RELEASE_CYCLE.md`. Shape rule 1 (no job-level `if:`) is unaffected.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 03:07 PM_

Fixed in #1713, merged to `dev` (e665e56d). Reaches `main` with the next train or via the lane itself; the timeout residual is tracked in #1712.

