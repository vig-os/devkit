---
type: issue
state: closed
created: 2026-08-13T08:02:08Z
updated: 2026-08-13T09:17:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1487
comments: 1
labels: bug, area:ci
assignees: none
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:09.292Z
---

# [Issue 1487]: [[BUG] Upstream promote-release checks the PR approval only in merge — after :latest moved and the release was published](https://github.com/vig-os/devkit/issues/1487)

### Description

devkit's own `promote-release.yml` checks the release PR's **draft status and
approvals only in the `merge` job**, which runs *after* `promote` has already
moved GHCR `:latest` and published the draft GitHub Release. A release PR that is
draft, unapproved, or CI-red therefore fails the promote **after** its two
irreversible-ish effects have landed, leaving the release published but unmerged.

The scaffolded consumer template does not have this shape: it performs the same
`Find and verify release PR` check in **`validate`** (fail-fast, before `promote`)
*and* repeats it in `merge`. Only the upstream workflow is missing the early gate.

| | `validate` | `promote` | `merge` |
|---|---|---|---|
| `.github/workflows/promote-release.yml` (devkit) | version/arch, GHCR images, cosign, draft release, downstream gate — **no PR check** | moves `:latest`, publishes the release | **first** PR draft/approval/CI check (`:405-465`) |
| `assets/workspace/.github/workflows/promote-release.yml` (consumers) | **PR draft/approval/CI check** (`:181-222`) | same | repeats the check (`:394-433`) |

### Steps to Reproduce

1. Have a release PR for `X.Y.Z` that is not approved (or is still draft).
2. Dispatch `promote-release.yml` with `version=X.Y.Z`.
3. `validate` passes — it never looks at the PR.
4. `promote` moves `:latest` and runs `gh release edit "$VERSION" --draft=false`.
5. `merge` fails: `ERROR: PR #N does not have approvals`.

### Expected Behavior

The promote refuses before publishing anything, the way the consumer template
does — the approval gate is checked in `validate`.

### Actual Behavior

The run fails at `merge` with `:latest` already moved and the GitHub Release
already published, so the repository is left in a half-promoted state: the
release exists publicly, `main` does not contain the release commit, and the
release PR is still open. Recovery is to obtain the approval and re-run the
failed job — but the published release cannot be walked back, since published
releases are immutable org-wide and deleting one tombstones its tag name.

### Has this fired?

**No — it is latent.** Every promote run to date has succeeded
(`31604989709` 1.8.0, `31248884977`, `30913559426`, `30585083552`,
`30207909845`, `30021617295`). The reason is operator discipline: the maintainer
re-approves the release PR before dispatching promote.

That is precisely why this is worth fixing now rather than filing and forgetting.
[#1474](https://github.com/vig-os/devkit/issues/1474) established that a **final**
`release.yml` run's `finalize` job *always* pushes to the release branch and so
*always* dismisses the approval where stale-review dismissal is enabled — org-wide
in `vig-os`. The trigger condition for this defect is therefore the **default
state** of every final release, and until #1486 documented the re-approval step,
the only thing standing between it and a half-promoted release was an undocumented
habit.

### Possible Solution

Mirror the consumer template rather than inventing a new shape: lift the
`Find and verify release PR` check into `validate` and **keep** the copy in
`merge` (state can change between the two jobs — the consumer template keeps both
deliberately). That also removes an upstream/template divergence in a workflow
pair that is otherwise kept in step.

Note the `merge` copy resolves `PR_NUMBER` as a step output consumed further down,
so the lift is a duplication of the check, not a move of the whole step.

### Environment

devkit 1.8.0 / `dev` @4ec1c803, `.github/workflows/promote-release.yml`
(`validate` `:39`, `promote` `:299`, `merge` `:380`).

### Changelog Category

Fixed

Refs: #1474, #902

---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 09:17 AM_

Fixed on `dev` via #1490 (merge commit `7c252876`).

The gate now runs in `validate`, before `promote` moves `:latest` or publishes the Release; the `merge` copy stays, since PR state can change between the two jobs. Mirroring the consumer template wholesale also brought the mergeability gate (#1132 — BEHIND/BLOCKED/DIRTY), which the upstream workflow had never carried in *either* job.

`tests/test_promote_release.py` is now parametrized over both copies rather than pinning the scaffold alone — the divergence was invisible precisely because the shape suite only ever looked at the template. All four `[devkit]` cases were RED before the fix.

Closing manually — a `Closes` line in a PR targeting `dev` does not auto-close (GitHub only honours it on the default branch).

