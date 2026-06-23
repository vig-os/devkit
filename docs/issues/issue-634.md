---
type: issue
state: open
created: 2026-06-23T06:54:07Z
updated: 2026-06-23T06:55:02Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/634
comments: 0
labels: feature, area:image
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:49.968Z
---

# [Issue 634]: [T2.1 — Nix-built devcontainer image (`buildLayeredImage`), non-publishing](https://github.com/vig-os/devcontainer/issues/634)

Tracking: #625



## Context

Build the devcontainer image **with Nix itself** (`dockerTools.buildLayeredImage` /
`streamLayeredImage`) rather than a Dockerfile `FROM`, so the Nix package manager (CppNix or
`pkgs.lix`) is included as a closure layer and `nix`/`direnv` are live inside the container,
identical to the direnv path. This refines the "base = `nixos/nix`" decision: same outcome
(nix CLI live in the container, minimal — no NixOS distro), but assembled by Nix so the build
is **bit-reproducible** (the master's "identical image digest" acceptance criterion holds —
a Dockerfile `FROM` build would not be reproducible). `nix2container` stays reserved for
downstream production images. This is the discovery phase for FHS breakage and ships behind
`continue-on-error` until the portable test suite (#635) is in place.

## Scope

**In:**
- `packages.devcontainerImage` = `dockerTools.buildLayeredImage` (or `streamLayeredImage`)
  whose contents include the Nix package manager (CppNix or `pkgs.lix`) + a baked flake dev
  profile (`nix profile install .#devShell` or an equivalent baked `nix develop` profile).
- Reproduce the workspace-bootstrap layers the Debian build provides:
  - locale via `glibcLocales` + `LOCALE_ARCHIVE` (no `locale-gen`),
  - `/root/assets`,
  - pre-commit cache,
  - template `.venv` via Nix's uv/python with `UV_PYTHON_DOWNLOADS=never` +
    `UV_PYTHON=<nix python314>`.
- New CI job builds the image + runs testinfra `continue-on-error: true`.
- **In-container evaluator** decided here (CppNix as shipped vs add `pkgs.lix`).

**Out:**
- Publishing the image (#639).
- Multi-arch (#636).

## Tasks

- [ ] Add `packages.devcontainerImage` via `buildLayeredImage` (nix CLI in the closure)
- [ ] Bake the flake dev profile
- [ ] Reproduce locale / `/root/assets` / pre-commit cache / template `.venv` layers
- [ ] Add the non-publishing CI build + testinfra job (`continue-on-error`)
- [ ] Decide the in-container evaluator included in the closure (CppNix vs `pkgs.lix`)

## Acceptance criteria

- Image builds.
- Portable testinfra (#635) passes against it.
- Rebuild from the same `flake.lock` on another host yields an identical image digest.
- Final image size is recorded and within budget (target: ≤ the current Debian `:slim` image;
  flag and justify if the closure exceeds it).

## Dependencies

- **Depends-on:** #631, #628.
- **Blocks:** #636, #637, #639.

## Files

- `flake.nix`
- `.github/workflows/*`

## Test notes

- Uses #635's portable assertions; expect the first run to surface FHS gaps (missing shell
  utilities, locale archive, paths). Iterate image contents until green.

## Related issues

- **#545** (bake agent-CLI toolkit + Claude Code) — carry its image-level requirements here:
  `claude` on PATH, `ENV IS_SANDBOX=1` (bypasses the uid-0 check for
  `--dangerously-skip-permissions`; the container is the trust boundary), and `cc`/`cld`
  aliases. The tool list itself lands in `devTools` (#631). Its ~+200 MB apt/binary approach is
  replaced by the Nix closure.
- **#40** (Migration to prek) — the pre-commit cache layer is rebuilt here; this is the moment
  to decide `pre-commit` vs `prek` (both packaged in nixpkgs).

