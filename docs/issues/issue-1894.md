---
type: issue
state: open
created: 2026-10-14T20:32:42Z
updated: 2026-10-14T20:32:42Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1894
comments: 0
labels: docs, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:42.723Z
---

# [Issue 1894]: [[DOCS] Build stack explainer: edit loop vs hermetic gate vs artifact, crane's role and limits, and a dated nixifier matrix](https://github.com/vig-os/devkit/issues/1894)

### Description

devkit ships crane (`mkRustProject`), dev shells, Cachix wiring and worktree recipes, but no document says how they fit together. Nobody can tell which layer answers which question. Users either push every edit through `nix flake check` (slow) or bypass Nix entirely (CI and local disagree). The same gap exists for picking a "nixifier", the tool that turns a language's lockfile into Nix derivations, for languages other than Rust.

### Documentation Type

New page: a design/architecture explainer (e.g. `docs/BUILD_STACK.md`), linked from `NIX.md` and the Rust pack docs.

### Target Files

`docs/BUILD_STACK.md` (new), `docs/NIX.md`, the Rust module docs.

### Proposed content

**1. Three layers, one rule each**

| layer | answers | tooling | properties |
|---|---|---|---|
| **Edit loop** | "does my change compile/pass, *now*?" | plain `cargo check/clippy/nextest`, rust-analyzer in the dev shell; sccache (#1889), per-worktree build dirs (#1888) | incremental, impure, seconds |
| **Gate** | "is this commit correct?" | `nix flake check`: crane `cargoClippy`, `cargoNextest`, `cargoDocTest`, `cargoDeny`, fmt, doc | hermetic, sandboxed, content-addressed, cacheable, minutes |
| **Artifact** | "what do we ship?" | `nix build .#pkg`: the same crane derivations, reusing the gate's `cargoArtifacts` | the shipped binary is built from the dependency artifacts the tests ran against |

The rule: iterate in layer 1, decide in layer 2, ship from layer 3. CI must run layer 2 (see #1811). Layer 1 is never the source of truth, and layer 2 is never the inner loop.

**2. What crane gives, and what it doesn't**

- `buildDepsOnly` compiles the dependency graph once per `Cargo.lock` + toolchain. Every check and the package reuse it through `cargoArtifacts`.
- Outputs are store paths. Same inputs give the same hash, so they can be substituted from the binary cache by every CI run, laptop and remote builder. Re-running an unchanged gate costs nothing.
- Works naturally on remote builders (`builders = ssh-ng://…`, `max-jobs = 0`), so heavy checks can be queued on a build host.
- **Not for the edit loop:** no incremental compilation of workspace crates, a flake evaluation per run, sandboxed tests (no network or `$HOME`).
- **Coarse dependency caching:** one `Cargo.lock` bump rebuilds the whole dependency derivation. Per-crate tools (below) trade Nix complexity for finer granularity.
- **No compile caches inside derivations.** sccache would need sandbox holes (`extra-sandbox-paths` / `__impure`), which break purity and let a poisoned cache entry spread through the binary cache under a "verified" hash. `cargoArtifacts` is the cache. See #1889.

**3. Choosing a nixifier**

State it as of a date, since these move. Status checked 2026-10-14 against each project's repo and README:

| ecosystem | recommended | alternatives | avoid / notes |
|---|---|---|---|
| Rust | **crane** (active, v0.24.0, 2026-08) | **crate2nix** (active, 0.15.0, 2026-01) for per-crate derivations and fine-grained caching in large workspaces; **naersk** (simpler, fewer knobs); nixpkgs `buildRustPackage` for nixpkgs-style packaging (single derivation, no deps/check split) | **cargo2nix**: no push since 2025-06 |
| Rust toolchain | **fenix** or **rust-overlay**, both active. Document the trade-off: fenix `fromToolchainFile` needs a hash refresh per toolchain bump, rust-overlay is hash-free | nixpkgs `rustc`/`cargo` when the nixpkgs version suffices | |
| Python (uv) | **uv2nix** on **pyproject.nix** (active; lockfile-driven) | dev shell + `uv sync` (non-hermetic, layer 1 only) | **poetry2nix**: its README now says "⚠️ Unmaintained ⚠️". Migrate Poetry projects to uv + uv2nix |
| JS/TS | nixpkgs `buildNpmPackage` / `importNpmLock` (npm), `pnpm` fetchDeps helpers (pnpm) | **dream2nix** (multi-ecosystem, active) | hash-only FODs without a lockfile |

For each: what is hashed (lockfile vs FOD hash), how deps are cached, how it behaves on remote builders, and the update chore (hash refresh on dep bump).

**4. Caching map:** which cache serves which layer. sccache for layer 1; the Nix binary cache (Cachix today, any substituter) for layers 2 and 3, pushed from trusted branches only (#1784, #1881).

### Related Code Changes

#1811 (CI runs no layer 2), #1784, #1881, #1886, #1887, #1888, #1889.

### Acceptance Criteria

- [ ] `docs/BUILD_STACK.md` with the three-layer table, crane strengths and limits, the dated nixifier matrix, and the caching map.
- [ ] Linked from `NIX.md`, the Rust module docs and the generated workspace README.
- [ ] Nixifier statuses carry a "checked on" date and the source (repo, README, release).

### Changelog Category

Added

