---
type: issue
state: closed
created: 2026-07-21T09:16:09Z
updated: 2026-07-21T11:58:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1237
comments: 1
labels: feature, area:ci, effort:small, security
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:38.446Z
---

# [Issue 1237]: [Scheduled security scan covers main only — add a dev-ref vulnix scan lane](https://github.com/vig-os/devkit/issues/1237)

## Description

`security-scan.yml` runs the nightly vulnix gate (05:00 UTC) from the default branch, so it scans **main's** image closure — the right primary target, since that's what consumers run. But `dev`'s closure is only ever scanned at RC time (or by manual dispatch, as the workflow header itself notes). Gate surprises are cheapest to discover *before* a release branch is cut.

## Problem Statement

Two failure modes currently surface only mid-release-train:

- A weekly `nixpkgs-unstable` bump (or any dev change) introduces an unexcepted HIGH/CRITICAL into the dev closure; nothing scans it until an RC run trips the gate.
- A time-boxed `.vulnixignore` exception expires (e.g. the gawk exception expiring 2026-07-28) and the first run to notice is the one gating a release.

Both have bitten release trains before; a scheduled dev scan turns them into an ordinary tracking issue days earlier.

## Proposed Solution

Add a `dev`-ref lane to `security-scan.yml`: a second scheduled job (or matrix leg) that checks out `ref: dev` and reuses the existing machinery unchanged — `check-expirations`, closure build of `devkitImageEnv` (Cachix-backed, so cheap), vulnix via the nvd-mirror, `vulnix-gate` against dev's own `.vulnixignore`, and the deduplicated tracking-issue step (with a dev-distinct issue title so the two lanes don't collide on dedup).

Nightly or weekly cadence both work; if nightly, stagger after the main scan so the weekly-keyed NVD cache is warm.

Drive-by in the same file: the schedule comment ("staggered after nightly CI at 04:00 UTC") is stale — no workflow has a 04:00 schedule anymore.

## Alternatives Considered

- **Scheduled nightly build of dev**: rejected (investigation 2026-07-21) — the flake is fully pinned, so a cron rebuild re-proves what push-triggered CI already proved; `nix-dev` (see #1236) stays the only rolling artifact. The security gap needs a *scan*, not a build or publish.
- **Status quo (RC-time scanning)**: works but pushes discovery of gate failures to the most expensive moment.

## Impact

- Backward compatible; no published artifacts change.
- Adds one scheduled closure build+scan per cadence tick — closure comes from Cachix, NVD data from the vig-os mirror, so runtime cost is minutes.

## Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:58 AM_

Fixed on dev via PR #1244 (merge commit d829e735): security-scan.yml gains a ref matrix (main, dev) with fail-fast: false, ref-distinct tracking-issue titles and ref-scoped artifacts. Note: schedule fires from main only, so the dev lane goes live at the next promote (workflow_dispatch works meanwhile). Ships with 1.4.1.

