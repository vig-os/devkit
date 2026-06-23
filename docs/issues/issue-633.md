---
type: issue
state: open
created: 2026-06-23T06:54:05Z
updated: 2026-06-23T06:55:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/633
comments: 0
labels: feature, area:image, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:50.394Z
---

# [Issue 633]: [T1.3 — direnv onboarding (nix-direnv)](https://github.com/vig-os/devcontainer/issues/633)

Tracking: #625



## Context

`.envrc` uses bare `use flake`, which re-evaluates on every entry and risks the dev-shell
closure being garbage-collected. `nix-direnv` adds a GC-rooted, cached evaluation so
re-entry is instant — the non-container onboarding fast path.

## Scope

**In:**
- Switch `.envrc` to **nix-direnv** (GC-rooted, cached).
- Document the clone → `direnv allow` flow + the Cachix substituter in `CONTRIBUTE.md`.

**Out:**
- The downstream template stub (#640).

## Tasks

- [ ] Update `.envrc` to use nix-direnv
- [ ] Document onboarding + Cachix substituter in `CONTRIBUTE.md`

## Acceptance criteria

- A clean clone + `direnv allow` yields a working shell in seconds on a warm cache.

## Dependencies

- **Depends-on:** #631.
- **Blocks:** none.

## Files

- `.envrc`
- `CONTRIBUTE.md`

## Test notes

- Manual onboarding check; ensure the documented Cachix substituter avoids a from-source
  build on first `direnv allow`.

## Related issues

- **#255** (Document Nix flake as alternative dev setup) — **superseded by this issue.** Fold
  in its specifics: target `docs/templates/CONTRIBUTE.md.j2` (the source template, not the
  generated `CONTRIBUTE.md`), document enabling the `nix-command` + `flakes` experimental
  features, and regenerate with `just docs`. Close #255 when this lands.

