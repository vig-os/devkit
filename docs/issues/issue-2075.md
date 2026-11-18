---
type: issue
state: open
created: 2026-11-14T04:44:23Z
updated: 2026-11-14T05:11:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2075
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-14T08:50:46.450Z
---

# [Issue 2075]: [ci.yml: Tests 20-min timeout is consumed by uncached toolchain setup (2–7 min) on ephemeral self-hosted pods](https://github.com/vig-os/devkit/issues/2075)

## Problem

On self-hosted ARC runners, every pod starts with an empty Nix store, so `Set up devkit toolchain` re-substitutes the whole devshell each time. That one step uses a large, highly variable share of the fixed `timeout-minutes: 20` on the `Tests` job (ci.yml, unchanged in 1.19). Once a consumer's suite grows past roughly 12 minutes, the job is cancelled on most runs, and there is no repo-level knob to change that.

## Evidence (exo-pet/MPECT, `ksb-exo-pet-large`, 8 xdist workers, one run in flight)

| Run | Set up devkit toolchain | Run tests | Result |
|---|---|---|---|
| 43514723040 | 2 m 10 s | 11 m 06 s | green |
| 43534287934 | 7 m 19 s | 10 m 02 s | green (18.7 m total) |
| 43542521457 attempt 4 | **6 m 40 s** | 13 m+ (95 % at cancel) | "exceeded the maximum execution time of 20m0s" |

On attempt 4, `Sync project dependencies` took 13 s, so uv is not the cost; the Nix toolchain realisation is. Attempts 1–3 of the same run were cancelled the same way: Tests at 20 min and Lint at 15 min.

## Asks (root cause first)

1. Make toolchain setup cheap and predictable on ephemeral self-hosted pods: a persistent or shared Nix store or substituter for ARC pods, or confirm that `CACHIX_CACHE` is actually being hit. That setup step should take seconds, not 2–7 minutes.
2. Then make the lane timeout a documented consumer setting, alongside `DEVKIT_CI_LANE_SIZES`, so a repo with a legitimately longer suite isn't capped by a scaffold constant. Related: #1874 (release-core, same fixed 20 min) and #2060 (Resolve toolchain 2 min).

---

# [Comment #1]() by [gerchowl]()

_Posted on November 14, 2026 at 05:11 AM_

Root cause on the fleet side: exo-pet/exo-fleet#1102 (the cache.nixos.org pull-through proxy refuses pod connections) and #1087. The devkit ask here is mainly item 2 (a configurable lane timeout); item 1 belongs to the fleet.

