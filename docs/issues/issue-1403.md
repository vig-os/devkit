---
type: issue
state: closed
created: 2026-08-10T13:08:13Z
updated: 2026-08-10T14:12:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1403
comments: 2
labels: bug, priority:medium, area:workflow, effort:medium, semver:patch
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:25.988Z
---

# [Issue 1403]: [[BUG] main→dev sync PR conflicts on every release (frozen changelog heading + issue/PR snapshots)](https://github.com/vig-os/devkit/issues/1403)

## Description

Every release, the automated `main → dev` sync PR opens **conflicted** and needs a
manual resolution round-trip. It has now happened on consecutive releases:

- vig-os/devkit#1395 — resolved by `dc25bfbb` "resolve sync conflicts by taking dev-side issue/PR snapshots"
- vig-os/devkit-smoke-test#351 — resolved by `6b8b130` "resolve sync conflicts by taking main-side release changelog and pr-350 snapshot"

The conflicts are deterministic and always resolve the same mechanical way, so
this is automatable rather than something a human should adjudicate each time.

There are **two independent root causes**.

### Root cause A — the deploy step rewrites an already-frozen `## [X.Y.Z]` heading

On `devkit-smoke-test`, merge base `f1b0505` ("freeze changelog for release 1.7.0")
had:

```
## [1.7.0] - TBD
```

Both branches then rewrote that same line, differently:

- **main** `bb0df1f` (finalize release) →
  `## [1.7.0](https://github.com/vig-os/devkit-smoke-test/releases/tag/1.7.0) - 2026-08-08` ✅
- **dev** `78191d5` (`chore: deploy 1.7.0`) →
  `## [1.7.0](https://github.com/vig-os/devkit/releases/tag/1.7.0) - 2026-08-07` ❌

Two different rewrites of one line from a common base is a guaranteed content
conflict. The dev-side value is also wrong on both counts: it points at
**devkit's** release rather than the consuming repo's own, and carries devkit's
release date instead of the consumer's.

The same commit additionally *moved* the deploy entry out of the frozen `[1.7.0]`
section back up into `## Unreleased`, producing a second conflicting hunk.

Both edits violate the project's own changelog rule — *"Never modify entries
below `## Unreleased`"*. The `## [X.Y.Z] - TBD` placeholder is owned by
`prepare-release` / `finalize` on the release branch; the deploy step must not
touch it.

**Scope:** the collision requires the consumer's own version to equal the devkit
version being deployed, which structurally only holds for `devkit-smoke-test`.
But the underlying behaviour — matching and rewriting an existing released
heading, and stamping devkit's URL/date into it — is wrong for any consumer where
the versions ever coincide.

### Root cause B — issue/PR snapshots add/add-conflict on every sync

`docs/issues/*.md` and `docs/pull-requests/*.md` are generated independently on
both branches by the sync-issues runs, at different times:

- `main` `2b1432a1` wrote `docs/pull-requests/pr-350.md` with `state: closed (merged)`, `synced: 2026-08-09T03:41:00Z`
- `dev` `fb536bf`/`13a1aa7` wrote the same path with `state: open`, `synced: 2026-08-08T07:50:54Z`

Neither branch has the file at the merge base → **add/add conflict**. This
affects **every gitflow repo**, not just the smoke-test; it is what caused
devkit#1395 on its own.

Resolution is always mechanical: keep the later-synced snapshot (post-release,
that is always main's).

## Steps to Reproduce

1. Run a release train to completion in a gitflow repo (freeze → finalize → merge to `main`).
2. Let `sync-main-to-dev.yml` fire on the push to `main`.
3. Observe the PR opens with title `chore: sync dev with main (conflicts)` and the `merge-conflict` label.
4. Inspect: `git merge-tree --write-tree --name-only origin/dev origin/main`

## Expected Behavior

The post-release `main → dev` sync PR is conflict-free and auto-merges, because:

- no branch other than the release branch ever rewrites a `## [X.Y.Z]` heading, and
- deterministic generated artifacts (issue/PR snapshots) resolve automatically.

A human is only pulled in for a *genuine* semantic conflict.

## Actual Behavior

The sync PR opens conflicted every release. `sync-main-to-dev.yml` detects the
conflict via `merge-tree`, skips `Enable auto-merge`, labels `merge-conflict`,
and posts a manual runbook — so the release is not actually complete until
someone hand-resolves the same two conflict classes again.

## Environment

- Repos: `vig-os/devkit` (cause B), `vig-os/devkit-smoke-test` (causes A + B), all gitflow consumers (cause B)
- Workflow: `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- devkit version: 1.7.0
- Observed: 2026-08-08 → 2026-08-10

## Additional Context

The workflow header comment (lines 25–29) reasons that *"No CHANGELOG reset is
needed here … the merge therefore preserves `## Unreleased` instead of silently
dropping it (#590)"*. That reasoning is sound for **preserving `## Unreleased`**,
but it does not cover cause A, where the dev side rewrites an already-**released**
heading. The two are separate concerns.

## Possible Solution

**A.** Constrain the deploy/upgrade changelog writer to only ever insert under
`## Unreleased`. It must never match or rewrite an existing `## [X.Y.Z]` heading.
If the deployed devkit version needs recording, put it in the entry text, not the
section heading.

**B.** Auto-resolve the generated snapshot paths. Either:
- teach `sync-main-to-dev.yml` to resolve `docs/issues/*.md` and
  `docs/pull-requests/*.md` to the main side before pushing the sync branch
  (post-release main is always the later sync), or
- ship a merge driver for those paths via `.gitattributes`. Note the existing
  changelog union driver does **not** fire on GitHub-side merges, so a driver
  alone will not help unless the resolution happens in the workflow's own
  checkout.

**C.** With A and B handled, `merge-tree` should come back clean and the existing
`Enable auto-merge` step takes over — removing the per-release manual round-trip
entirely. Keep the conflict-detection + `merge-conflict` label path as the
fallback for genuine conflicts.

## Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 01:57 PM_

Fix is up in #1406 (both causes). One deliberate deviation from the proposal above: the snapshot conflicts are resolved to the **dev** side, not main's.

The `Signed commits` ruleset (`~ALL` refs, no bypass actors) means the workflow runner can only produce single-parent GitHub-signed commits via commit-action's GraphQL path — a merge commit taking main's side is impossible without a signing key. Aligning the sync branch's copies of the conflicted snapshots with dev's content makes both merge sides identical, so the conflict vanishes; snapshots are derived artifacts of live GitHub state, and dev's next nightly sync-issues run re-captures anything the release-time sync recorded (its updated-since cutoff predates it), so the cost is only a ≤24 h staleness window. Only paths `merge-tree` reports as conflicted are aligned — a snapshot updated only on main still merges cleanly and is untouched. Anything outside `docs/issues/` + `docs/pull-requests/` (or a delete/modify conflict) keeps the manual `merge-conflict` path.

**Rollout (corrected from an earlier version of this comment):** push-triggered workflows execute the workflow file at the pushed commit — the 1.7.0 promote's sync run demonstrably executed at `headSha bcb0a257`, the merge commit itself. The 1.7.1 merge commit on main will contain the new workflow, so **the sync run fired by the 1.7.1 promote is already the auto-resolving version**; full live proof arrives with 1.7.1, no extra release needed. Cause A proves at the first 1.7.1-rc smoke deploy.

**Zero-release proof already done:** replayed the new pipeline against the real 1.7.0 conflict state (`dc25bfbb`'s parents). Format assumption, parse, and allowlist all hold (4 conflicted paths incl. one *content* conflict, `issue-529.md`), and the automated dev-side result is byte-identical on all four files to the manual resolution actually committed in `dc25bfbb`.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 10, 2026 at 02:12 PM_

Fixed by #1406 (CI fully green, awaiting merge click into dev; classifier blocks agent merges).

Both causes addressed with TDD pairs:
- **A** — smoke deploys preserve the consumer's root `CHANGELOG.md` (root-anchored rsync exclude + scaffold bootstrap only when absent; the cp+`unprepare` block that stamped devkit's dated release headings into the consumer file is gone), and the deploy-entry seeding awk is bounded at the next release heading.
- **B** — `sync-main-to-dev` (both decoupled copies, cross-copy identity pinned by test) auto-resolves snapshot-only conflicts via a GitHub-signed commit-action commit aligning the sync branch with dev's copies, re-verifies with `git merge-tree`, and only then enables auto-merge; everything else keeps the manual `merge-conflict` path.

Verification: replay against the real 1.7.0 conflict state reproduced the manual resolution `dc25bfbb` byte-for-byte (details in the comment above); full local gates green (pre-commit all-files, pytest 510+566, full bats incl. #995 actionlint over rendered templates, integration test against a freshly built image).

Live proof lands with the 1.7.1 train itself: the promote merge commit carries the new workflow, so the promote-triggered sync run is already the auto-resolving version; cause A proves at the first 1.7.1-rc smoke deploy.

