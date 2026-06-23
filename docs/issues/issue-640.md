---
type: issue
state: open
created: 2026-06-23T06:54:16Z
updated: 2026-06-23T06:55:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/640
comments: 0
labels: feature, area:image, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:47.586Z
---

# [Issue 640]: [T4.2 — Downstream pattern: minimal flake stub (non-overwriting) + `nix2container` production builder](https://github.com/vig-os/devcontainer/issues/640)

Tracking: #625



## Context

Downstream repos consume the toolchain via a flake **input**, so "update the dev environment"
means bumping that input — it never overwrites user files. This mirrors the existing
`justfile.base → justfile.project → justfile.local` layering: a managed upstream + a
user-owned, never-overwritten local layer. Only a **minimal** flake ships here; richer
language shells are future work.

## Scope

**In:**
- Add a **minimal** downstream `flake.nix` scaffold:
  - `inputs.vigos.url = "github:vig-os/devcontainer"`,
  - `nixpkgs.follows = "vigos/nixpkgs"`,
  - a **placeholder** `extraPackages = pkgs: [ /* add project tools here */ ];` with inline
    instructions.
- Add `.envrc` (`use flake`).
- Mark both as **scaffold-once / never-overwrite** in `scripts/manifest.toml` (same class as
  `docker-compose.project.yaml` / `justfile.local`) so `sync_manifest.py` never clobbers user
  edits on a dev-env update.
- Document & scaffold **`nix2container` as the SSoT-derived builder for production/runtime
  images in other packages** (separate from the devcontainer image).

**Out:**
- Modular language shells (C++ / Geant4 / Data-Analysis) — **future work**. Document that the
  upstream flake can later expose `devShells.{cpp,geant4,dataAnalysis}` that users opt into,
  without changing this scaffold.
- The install picker (#641).

## Tasks

- [ ] Add the minimal downstream `flake.nix` scaffold with `extraPackages` placeholder
- [ ] Add the `.envrc` stub
- [ ] Mark both never-overwrite in `manifest.toml`; update `sync_manifest.py` if needed
- [ ] Document + scaffold the `nix2container` production-image builder pattern
- [ ] Document the future modular-shells extension point

## Acceptance criteria

- A downstream repo gets a working `flake.nix` + `.envrc`.
- A simulated dev-env update does **not** overwrite user `extraPackages`.
- The `nix2container` production-image example builds.

## Dependencies

- **Depends-on:** #639, #633.
- **Blocks:** #641.

## Files

- `assets/workspace/flake.nix`
- `assets/workspace/.envrc`
- `scripts/manifest.toml`
- `scripts/sync_manifest.py`
- docs

## Test notes

- Add a sync test asserting never-overwrite behaviour for the flake / `.envrc` file class.

