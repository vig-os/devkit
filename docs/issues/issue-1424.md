---
type: issue
state: closed
created: 2026-08-11T12:39:59Z
updated: 2026-08-11T14:15:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1424
comments: 1
labels: feature
assignees: none
milestone: 1.7.1
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:04.876Z
---

# [Issue 1424]: [[FEATURE] sync-issues mirror mode: sync + fold the snapshot archive into the release branch at finalize, reset the mirror after promote](https://github.com/vig-os/devkit/issues/1424)


## Description

For consumers with `DEVKIT_SYNC_TARGET` set (the protected-`main` mirror mode
from #1227/#1228), make the release train the mirror's integration point:

1. At `release-core.yml` finalize (final leg), run one last sync-issues pass
   **onto the mirror**, then fold the mirror's snapshot archive
   (`docs/issues/`, `docs/pull-requests/`) into the release branch — replacing
   the release-branch sync dispatch in mirror mode — so the full, fresh
   archive reaches `main` through the human-approved release PR.
2. At `promote-release.yml` (after the release PR has merged), force-reset the
   mirror to `main` HEAD so it re-diverges only by post-release snapshot
   commits instead of indefinitely.

## Problem Statement

Mirror-mode consumers currently have **no path for the issue archive to ever
reach `main`**, and the existing release-time sync leg silently produces a
partial archive if it runs:

1. The mirror doctrine (`docs/MIGRATION.md`, "Point sync-issues at an
   unprotected mirror branch") says the mirror "diverges permanently and is
   never merged back". Live evidence on the only mirror-mode consumer,
   `vig-os/org-config` (devkit 1.7.0, `sync/issue-mirror`): nightly syncs are
   green, the mirror is 12 ahead / 76 behind `main`, and `main` carries **no
   `docs/issues/` at all** despite two published releases.
2. The release-time sync in `release-core.yml` (Trigger sync-issues → Wait →
   Pull) is an **incremental top-up**: the sync state cache key
   (`sync-issues-state-<repo>`) is repo-wide and shared with the nightly mirror
   runs, so a release-branch dispatch restores last night's cutoff and syncs
   only ~1 day of deltas. In mirror mode the release branch is cut from a
   `main` that has no archive, so `main` would only ever accumulate partial
   snapshots and never converge — mirror mode and the release-time sync do not
   compose today.
3. Worse, if that release-branch dispatch *does* run in mirror mode, it
   advances the shared state cutoff, and the mirror's next nightly run syncs
   only from the new cutoff: every issue/PR updated between the mirror's last
   nightly and the release **permanently misses the mirror**. Gitflow is
   immune (release-branch sync results flow back to `dev` via
   sync-main-to-dev), but the mirror has no backflow — so the mirror must
   remain the *only* sync target.
4. The mirror also diverges from `main` without bound (org-config: 76 behind
   after ~2 months), even though its content after each release is fully
   contained in `main`.

A PR-based sync mode was evaluated and deferred in #1228 (per-sync human
approval is inherent toil). This proposal is the cheap variant of that revisit:
piggyback on the release PR, which is already human-approved, so no extra
approvals are introduced and the nightly cadence stays off `main` entirely.

## Proposed Solution

**Finalize (release-core.yml, final leg only) — sync the mirror, then fold.**
In mirror mode, the existing "Trigger sync-issues workflow" step dispatches
onto the **mirror** (its normal target: `--ref` the release branch so the
release's own workflow definition runs, but `target-branch=<mirror>`) instead
of the release branch, and after the existing wait a fold step lands the
result on the release branch:

- One last incremental sync onto the mirror, so the archive is fresh as of
  the release and the shared state cutoff stays owned by mirror-targeted runs
  (no split-brain with the nightly cadence).
- Fetch the mirror; if it does not exist (never bootstrapped), log and no-op.
- `git checkout <mirror> -- docs/issues docs/pull-requests` (paths only —
  never a branch merge, so the mirror's divergence and staleness relative to
  `main` are irrelevant) and commit the result to the release branch via
  commit-action (signed, single-parent). Same resolution shape as the
  sync-main-to-dev snapshot auto-resolve (#1403).
- No release-branch sync dispatch remains in mirror mode; non-mirror
  consumers keep today's behavior bit-for-bit.

**Promote (promote-release.yml) — regenerate the mirror.** After the release
PR has merged, `main` contains exactly the snapshot the release carried, so a
rendered step force-resets the mirror ref to `main` HEAD (API ref update,
`force: true`, commit App token — the mirror is unprotected by design). The
mirror's history is regenerated state, so nothing is lost; divergence is
thereafter bounded to snapshot commits since the last release. A nightly sync
run racing the reset is benign: the next nightly regenerates any clobbered
delta (self-healing, as today).

Realization: scaffold-time, like the other `#1228` knobs —
`render_sync_settings` in `init-workspace.sh` rewrites the sync-dispatch
target and injects the fold + reset steps only when `DEVKIT_SYNC_TARGET` is
set (empty manifest key => byte-identical scaffolds, no behavior change for
every existing non-mirror consumer). Keyed on the knob, not the workflow
model: a gitflow consumer that sets a mirror target would have the same gap.

Docs: amend the mirror doctrine in `docs/MIGRATION.md` — the mirror never
merges *directly* into `main` and remains the live self-healing archive
between releases; its snapshot dirs are folded into `main` release-by-release
via the release PR, and the branch is re-based onto `main` at each promote.

## Alternatives Considered

- **Fold the stale mirror, then run the release-branch sync on top** — reuses
  today's dispatch, but the release-branch run advances the shared state
  cutoff and the mirror permanently misses the inter-sync window (problem 3
  above). Rejected in favor of sync-the-mirror-then-fold.
- **Dispatch the release-time sync with `force-update=true` in mirror mode** —
  no new fold step, but a full-history rebuild on every release costs API rate
  proportional to repo history (the bounded-lookback/cache design exists
  precisely to avoid this) and makes the release-critical path slower and less
  reliable. Rejected.
- **Delete the mirror at promote instead of resetting it** (next nightly
  bootstrap recreates it from `main`) — equivalent end state, but leaves an
  archive-less window until the next nightly and loses the ability to dispatch
  a manual sync in between; the force-reset is one API call. Rejected.
- **Per-run PR-based sync mode** — already evaluated and deferred in #1228;
  unchanged.
- **Keep the doctrine (mirror never reaches `main`)** — status quo; `main`
  permanently lacks the archive on exactly the consumers whose `main` is most
  tightly governed.

## Additional Context

- #1227 (direct push vs require-PR rulesets, first seen on org-config),
  #1228 (`DEVKIT_SYNC_TARGET`/`DEVKIT_SYNC_SCHEDULE` knobs), #1403
  (snapshot auto-resolve pattern in sync-main-to-dev).
- Out of scope: trunk consumers currently direct-pushing to unprotected
  `main` (exo-fleet, vault, playground-carlos — no rulesets), h5v (pre-devkit,
  migration PR h5v#2 open), and any ruleset normalization of those repos. If
  they later gain `main` protection, setting `DEVKIT_SYNC_TARGET` opts them
  into this mechanism with no further devkit work.
- Freshness trade-off (accepted): `main`'s archive is only as fresh as the
  last release; the mirror remains the live archive between releases.

## Impact

- Benefits mirror-mode consumers (today: org-config; tomorrow: any
  protected-`main` trunk consumer).
- Backward compatible: no-op unless `DEVKIT_SYNC_TARGET` is set; non-mirror
  scaffolds stay byte-identical.

## Changelog Category

Changed

## Acceptance Criteria

- [ ] Scaffold with `DEVKIT_SYNC_TARGET` set renders, in `release-core.yml`
      finalize (final leg only): sync dispatch retargeted to the mirror
      (workflow `--ref` still the release branch), then the fold step; no
      release-branch sync dispatch remains. Unset target renders
      byte-identical `release-core.yml` and `promote-release.yml`.
- [ ] Fold copies only `docs/issues/` and `docs/pull-requests/` from the
      mirror; commits via commit-action (signed); no-ops cleanly when the
      mirror branch is absent or the dirs are missing/empty.
- [ ] The release-time mirror sync runs before the fold, so the folded archive
      is fresh as of the release; the shared sync-state cutoff is only ever
      advanced by mirror-targeted runs.
- [ ] `promote-release.yml` (knob set) force-resets the mirror ref to `main`
      HEAD after promote, via the commit App; step is a no-op when the mirror
      is absent.
- [ ] `docs/MIGRATION.md` mirror doctrine updated ("never merged back" →
      "folded into the release PR at finalize, reset onto `main` at promote").
- [ ] bats coverage for the render (knob set/unset), dispatch retarget, fold
      ordering, and the promote reset step.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 02:15 PM_

Implemented in #1426, merged to dev @4822b706 (closed manually — dev-PR `Closes` does not auto-close).

- `release-core.yml` (mirror mode): final-leg sync dispatch retargets to the mirror; fold steps land `docs/issues/` + `docs/pull-requests/` on the release branch before the finalize SHA is captured
- `promote-release.yml` (mirror mode): `reset-sync-mirror` job force-pushes the mirror onto `main` after the release PR merges
- Unset `DEVKIT_SYNC_TARGET` renders byte-identical templates (pinned by test); mirror render covered by a dedicated actionlint bats case
- MIGRATION.md doctrine amended; changelog entry under `## Unreleased`

Live proof: org-config's first devkit-train release after adopting 1.7.1.

