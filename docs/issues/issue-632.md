---
type: issue
state: open
created: 2026-06-23T06:54:03Z
updated: 2026-06-23T06:55:16Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/632
comments: 0
labels: area:ci, area:image
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:50.816Z
---

# [Issue 632]: [T1.2 — CI provisions tooling via the flake](https://github.com/vig-os/devcontainer/issues/632)

Tracking: #625



## Context

CI currently installs tools ad hoc in the build action. With the flake as SSoT (#631), CI
should obtain its tools from the flake via `nix develop`, proving the Cachix binary cache
under real CI load before any image risk is taken.

## Scope

**In:**
- Replace ad-hoc tool installs with `nix develop`.
- Debian image still built unchanged.
- Keep the `type=gha` Docker cache alive in parallel.

**Out:**
- The Nix-built image (#634).

## Tasks

- [ ] Run build/test jobs inside the flake shell (`nix develop`)
- [ ] Remove ad-hoc install steps superseded by the flake
- [ ] Keep Docker `type=gha` caching intact

## Acceptance criteria

- CI jobs run inside the flake shell.
- Build time stays within budget with a warm Cachix cache.

## Dependencies

- **Depends-on:** #631.
- **Blocks:** none.

## Files

- `.github/actions/**`
- `.github/workflows/*`

## Test notes

- Existing suites must stay green; record cold-vs-warm cache build times for comparison.

