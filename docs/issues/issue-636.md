---
type: issue
state: open
created: 2026-06-23T06:54:10Z
updated: 2026-06-23T06:55:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/636
comments: 0
labels: area:ci, area:image
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:49.136Z
---

# [Issue 636]: [T2.3 — Multi-arch Nix image (amd64 + arm64)](https://github.com/vig-os/devcontainer/issues/636)

Tracking: #625



## Context

Downstream digest-pinning (and Renovate's digest manager in consuming repos) depends on a
multi-arch **index** digest. The Nix image must be published as an index covering linux/amd64
and linux/arm64, built natively to avoid slow/brittle cross-compilation or emulation.

## Scope

**In:**
- Native amd64 (`ubuntu-24.04`) + arm64 (`ubuntu-24.04-arm`) CI matrix building
  `packages.devcontainerImage`.
- Push per-arch tags.
- `docker buildx imagetools create` the multi-arch index.
- Ensure the arm64 closure is in Cachix.

**Out:**
- The publish-cutover (#639).

## Tasks

- [ ] Add the amd64 + arm64 CI matrix
- [ ] Push per-arch tags
- [ ] Assemble the multi-arch index with `imagetools create`
- [ ] Confirm arm64 closure is cached in Cachix

## Acceptance criteria

- `docker buildx imagetools inspect …:<tag>` shows an index with amd64 + arm64.
- Downstream digest-pin resolves unchanged.

## Dependencies

- **Depends-on:** #634.
- **Blocks:** #639.

## Files

- `.github/workflows/*`
- `.github/actions/**`

## Test notes

- Verify the index digest shape matches what downstream digest-pinning expects (top-level
  index, not a single-arch manifest).

