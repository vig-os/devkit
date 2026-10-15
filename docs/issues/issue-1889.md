---
type: issue
state: open
created: 2026-10-14T19:40:23Z
updated: 2026-10-14T19:40:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1889
comments: 0
labels: feature, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:45.330Z
---

# [Issue 1889]: [[FEATURE] Rust: opt-in sccache for the dev shell (persistent dir, never inside crane derivations)](https://github.com/vig-os/devkit/issues/1889)

### Description

devkit has no compile-cache story for the Rust dev loop. Crane's `buildDepsOnly` caches dependencies at Nix granularity for `nix flake check` and packages, but local `cargo` in the dev shell (and in every worktree) recompiles the same dependency graph again and again.

### Problem Statement

- Every worktree and every clean rebuilds identical dependency crates.
- Downstream repos that want sccache end up hand-rolling it: wrapper scripts, `RUSTC_WRAPPER` in the shellHook, server lifetime and temp-dir fixes. Each reinvents the same pitfalls: a server endpoint or temp dir under a per-shell `TMPDIR` that disappears, cache size limits, and running inside builds where it can't work.

### Proposed Solution

An opt-in rust-module knob, e.g. `DEVKIT_RUST_SCCACHE=1` in `.vig-os` / `modules.rust.sccache = true`:

1. **Dev shell only.** Set `RUSTC_WRAPPER = sccache`, a persistent per-user `SCCACHE_DIR` (default `~/.cache/sccache`, not a per-shell temp dir) and `SCCACHE_CACHE_SIZE` with a sane default. Optional remote backend via the standard env vars (S3/WebDAV/Redis/GHA) for teams.
2. **Explicitly not inside crane derivations.** The Nix sandbox blocks it, and exposing it (`extra-sandbox-paths`, `__impure`) trades away reproducibility. Crane's `cargoArtifacts` is the cache for Nix builds. Say so in the docs, so nobody tries.
3. **Document the incremental interaction.** sccache skips incremental compilations, and cargo only compiles workspace members incrementally. Dependencies, the bulk, are cached, while the local crate keeps its incremental speed. No `CARGO_INCREMENTAL=0` is needed in the dev loop. CI is different: setting it there is a separate decision.
4. A `just cache-stats` recipe (`sccache --show-stats`) so users can see whether it's earning its keep.

### Alternatives Considered

- `Swatinem/rust-cache` in CI only: helps CI, not the local or worktree loop.
- Shared target dirs: lock contention (see #1888).

### Impact

Opt-in; no behaviour change unless enabled.

### Changelog Category

Added

