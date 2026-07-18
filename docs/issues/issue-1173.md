---
type: issue
state: closed
created: 2026-07-17T09:57:43Z
updated: 2026-07-17T11:35:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1173
comments: 1
labels: feature, priority:medium, area:ci, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:26.151Z
---

# [Issue 1173]: [Scaffolded ci.yml: manifest-driven runner override (self-hosted consumers can't keep hand-edits)](https://github.com/vig-os/devkit/issues/1173)

### Description

Let a consumer route the scaffolded `ci.yml` jobs to self-hosted runners via a `.vig-os` manifest key, instead of hand-editing a scaffold-managed workflow.

### Problem Statement

`assets/workspace/.github/workflows/ci.yml` hardcodes hosted runners. `exo-pet/exo-fleet` runs its CI entirely on a self-hosted runner (`[self-hosted, linux, x64, meatgrinder]`, per its ADR-0022 — GitHub billing blocked hosted runners for that org's heavy jobs). Because `ci.yml` is scaffold-managed, any hand-edit to `runs-on` is clobbered on the next re-scaffold/upgrade — so today a self-hosted consumer cannot adopt the scaffolded CI at all.

### Proposed Solution

- New optional `.vig-os` key, e.g. `DEVKIT_CI_RUNNER` (comma-separated label list; absent → current default, e.g. `ubuntu-24.04`).
- `resolve-toolchain` (which already reads `.vig-os`) emits a `runner-json` output (JSON array of labels, defaulted); downstream jobs use `runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}`. The `resolve-toolchain` job itself stays on the hosted default (it's seconds of sparse checkout; a consumer whose org can't run hosted jobs at all can be documented as a limitation or given a static render — keep v1 minimal).
- Persist the key through `init-workspace.sh` re-scaffolds like the other manifest keys (cf. #1116 DEVKIT_MODULES mirroring); optionally a `--ci-runner` installer flag.
- Document in `docs/MIGRATION.md`.

### Alternatives Considered

- Hand-edit + exclude ci.yml from the managed set: breaks the managed-upgrade model for the most churn-prone scaffold file.
- Repo variable (`vars.CI_RUNNER`) instead of `.vig-os`: viable, but the manifest is the established consumer-config SSoT and works without extra repo provisioning; `runs-on` can read `vars.*` directly though — acceptable fallback if expression-from-needs proves brittle.

### Additional Context

Recon from the exo-fleet deployment assessment (2026-07-17). exo-fleet's bespoke heavy workflows (nix build matrix, KVM NixOS tests) remain repo-specific beside the scaffolded ci.yml — this issue only covers the scaffolded lint/test/summary lanes. Related: #1039 (private-repo guards), ADR-conditional-container-toolchain.

### Impact

- Default unchanged for all existing consumers; opt-in via manifest. Backward compatible (semver:minor).

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 11:35 AM_

Shipped via PR #1174, merged to `dev` (dev-PR `Closes` does not auto-close — closing manually). Reaches consumers with the next devkit release.

