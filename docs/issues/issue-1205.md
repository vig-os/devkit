---
type: issue
state: open
created: 2026-07-17T20:26:34Z
updated: 2026-07-17T20:28:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1205
comments: 0
labels: feature, priority:medium, area:ci, area:workspace, effort:large, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:21.714Z
---

# [Issue 1205]: [Per-consumer workflow-model knob (gitflow default / trunk opt-in)](https://github.com/vig-os/devkit/issues/1205)

## Problem

The devkit scaffold + release cycle assume every consumer uses a `dev` branch with a `dev → release/X.Y.Z → main` gitflow plus `sync-main-to-dev`. This fits versioned-release repos (commit-action, sync-issues-action, devkit itself) but NOT trunk-style repos — surfaced by the exo-pet/exo-fleet rollout (a NixOS fleet repo that deploys from `main`), where provisioning created a `dev` branch and the full release apparatus the repo has no use for. See PR exo-pet/exo-fleet#230.

## Goal

A per-consumer **`DEVKIT_WORKFLOW`** knob (`gitflow` | `trunk`, **empty ⇒ gitflow**, the unchanged default) selecting the branching/release model.

- **gitflow (default, unchanged):** `dev` integration branch; cut `release/X.Y.Z` from `dev`; RC train; finalize merges to `main` + tag; `sync-main-to-dev` back-merges to `dev`.
- **trunk (opt-in):** `feature|bugfix|chore` straight to `main`; releases STILL happen but cut `release/X.Y.Z` **from `main`**, RC on it, merge back **into `main`** + tag. Only the `dev` branch and `sync-main-to-dev` disappear.

## Key findings (verified)

- `dev` is mechanically load-bearing in **exactly two** scaffolded workflows: `prepare-release.yml` (freeze + fork base) and `sync-main-to-dev.yml` (omit in trunk). The whole tag/build/publish/promote chain (`release-core.yml`, `release-publish.yml`, `promote-release.yml`) is ALREADY `release/* → main` and dev-free — **no changes needed there**.
- Every `dev` reference in `prepare-release.yml` is a plain branch **literal** (incl. the #617 read-after-write guard), so trunk is a precise **anchored literal render**, not a structural rewrite → **no workflow twin** (avoids the #1095 drift class).

## Architecture (decided)

**Scaffold-time render, everything** — realized entirely at install time (mirrors the `DEVKIT_MODE` structural precedent), NO resolve-toolchain runtime wiring, NO inert workflow files, NO twin. `on:` trigger branch filters are static YAML that can't be runtime-conditional, which is itself why scaffold-time is the only coherent single mechanism.

## Scope

Devkit **capability only**. exo-fleet #230 merges as-is on `dev` now; retrofitting exo-fleet/org-config to trunk + a trunk-aware ruleset bootstrap (#522) are separate follow-ups. Targets **1.5.0**; the in-flight 1.4.0 promote is independent and not blocked.

## Sub-issues (ordered 0 → 1 → {2,3} → 4 → 5)

- [ ] #1206 — SPIKE: prove release cut-from-main + merge-back + tag with no dev; prove scaffold render+exclude without breaking preview/#991 bats
- [ ] #1207 — manifest key `DEVKIT_WORKFLOW` + read/writeback + guards
- [ ] #1208 — scaffold render core (`render_workflow_model()` + copy-exclude/prune `sync-main-to-dev` + `--force` preview mirror)
- [ ] #1209 — install.sh `--workflow` flag + dev-branch creation gating
- [ ] #1210 — tests (`test_workflow_model.py` + bats + parametrize dev-assuming suites)
- [ ] #1211 — docs + ADR + plan doc

Full design plan retained by the maintainer (scaffold-time render; anchored literal render of prepare-release; compose-not-combine mode × model axes).

