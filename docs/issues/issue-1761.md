---
type: issue
state: open
created: 2026-09-29T08:27:15Z
updated: 2026-09-29T08:27:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1761
comments: 0
labels: feature, area:ci, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:47.702Z
---

# [Issue 1761]: [CI Summary cannot gate on jobs outside the managed ci.yml — consumers need a way to feed extra jobs into the aggregator](https://github.com/vig-os/devkit/issues/1761)

## Problem

The scaffolded `.github/workflows/ci.yml` is a managed file (regenerated on upgrade; local edits are lost). Its `summary` job — display name `CI Summary` — is the single required status check that vig-os/org-config's `Main` ruleset gates on for every tier-A repo (ADR-0008 in vig-os/org-config).

`summary.needs` is fixed to `ci.yml`'s own jobs:

```yaml
needs: [resolve-toolchain, lint, test, commit-checks, scaffold-drift, dependency-review]
```

A consumer that runs part of its CI in its own, non-managed workflow therefore has no way to make those jobs gate merges through `CI Summary`.

## Concrete case: vig-os/scitadel

scitadel's `.github/workflows/rust-ci.yml` runs:

- `Lint` — `cargo fmt --check` + `cargo clippy --workspace -- -D warnings`
- `Test (ubuntu-latest)` / `Test (macos-latest)` — a `cargo test --workspace` matrix

None of these can feed `CI Summary`, so with `CI Summary` as the only required check a red clippy or a failing macOS leg does not block a merge.

## Why the workarounds are not adopted

Both were evaluated under vig-os/org-config#294 and rejected (2026-09-29):

- **List the extra job names as additional required checks in org-config.** Required-check contexts are matched by name, so any job rename or matrix change silently breaks the gate (the check is never reported, or a new leg is never required). It also pushes per-repo CI layout into org config.
- **Bolt the tools onto the managed `lint` job via pre-commit hooks.** Slows every contributor's commit, and cannot cover a non-Linux leg such as `Test (macos-latest)`.

## Requirement

A supported, upgrade-safe way for a consumer repo to declare additional jobs — possibly defined in other workflow files — that `CI Summary` must wait on and fail with (same failure/cancelled semantics as the built-in jobs), so that a single required check keeps covering the repo's whole CI.

- Must survive `devkit-upgrade` without excluding `ci.yml` from upgrades or disabling the drift check.
- Consumers that declare nothing must be unaffected.

Design is left to devkit.

## Context

- Org-wide merge-protection audit: vig-os/org-config#294 (ADR-0008 tiers)
- Related downstream: vig-os/scitadel#227 (required-check set for scitadel's rulesets)

