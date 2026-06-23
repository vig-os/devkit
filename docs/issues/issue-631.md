---
type: issue
state: open
created: 2026-06-23T06:54:02Z
updated: 2026-06-23T06:55:20Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/631
comments: 0
labels: feature, area:ci, area:image
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:51.483Z
---

# [Issue 631]: [T1.1 — De-duplicate the flake into the real SSoT](https://github.com/vig-os/devcontainer/issues/631)

Tracking: #625



## Context

The `flake.nix` dev-shell and the `Containerfile` tool list are maintained independently and
drift; `flake.lock` is stale. This issue makes a single tool list the source of truth and
lays the reusable flake outputs the rest of the migration builds on.

## Scope

**In:**
- Factor a single `devTools` list.
- Bring the dev-shell to parity with the image toolset.
- Refresh `flake.lock`.
- Switch `nixpkgs` → pinned `nixos-25.05` + a secondary `nixpkgs-unstable` input overlaid for
  fast-movers (`uv`, `gh`).
- Add `lib.mkProjectShell`, `overlays.default`, and a `packages.devcontainerImage` stub.
- **Provision Cachix** (create the binary cache, generate the auth token, add
  `CACHIX_AUTH_TOKEN` as a repo secret) and wire it + a Nix installer in a **new,
  non-blocking** CI job. This provisioning is a prerequisite for every later track that
  relies on a warm cache (#633, T2.x).
- **Evaluator choice** decided here (Lix `lix-installer` vs Determinate/CppNix action) —
  swappable, no flake changes either way.

**Out:**
- The image build itself (#634).
- CI cutover to the flake (#632).

## Tasks

- [ ] Factor `devTools`
- [ ] Channel switch + unstable overlay for `uv`/`gh`
- [ ] Add reusable outputs (`lib.mkProjectShell`, `overlays.default`, image stub)
- [ ] Provision the Cachix cache + `CACHIX_AUTH_TOKEN` secret
- [ ] Add Cachix + Nix installer CI job (non-blocking)
- [ ] TDD: test `nix develop -c <tool> --version` per tool

## Acceptance criteria

- `nix develop` provides every tool in the toolset.
- Cachix cache exists and `CACHIX_AUTH_TOKEN` is configured; push works from CI.
- Existing CI is unaffected (new job is non-blocking).

## Dependencies

- **Depends-on:** none.
- **Blocks:** #632, #633, #634, #638.

## Files

- `flake.nix`
- `flake.lock`
- `.github/workflows/*`
- `tests/` (new flake test)

## Test notes

- The per-tool `nix develop -c <tool> --version` test is the TDD anchor; it also guards
  against future dev-shell/image drift.

## Related issues

- **#27** (Adopt Nix/devenv) — the originating proposal this issue executes. Preserve its
  intent: `flake.lock` as the controlled version document, hash-verified deps, SBOM (→ #637),
  air-gapped rebuild. Decide flake-vs-devenv here (roadmap = pure flake).
- **#545** (bake agent-CLI toolkit) — its tool list (rg/fd/bat/eza/delta/lazygit/zoxide/
  starship/freeze/expect/nvim + claude) should be **absorbed into `devTools`** rather than
  apt/curl-installed; the `EXPECTED_VERSIONS` drift #27 calls out is what this issue removes.

