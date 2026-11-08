---
type: issue
state: open
created: 2026-10-14T19:40:21Z
updated: 2026-10-14T19:40:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1888
comments: 0
labels: feature, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:45.952Z
---

# [Issue 1888]: [[FEATURE] Rust in many parallel worktrees: rust-analyzer target dir, copy-on-write warm start, build-dir, stale-build reclaim](https://github.com/vig-os/devkit/issues/1888)

### Description

devkit pushes a worktree-per-issue workflow (`justfile.worktree`), but its Rust support does nothing for the cost that workflow creates. Every new worktree starts with an empty `target/`, and rust-analyzer fights the CLI cargo for the same build lock. With several agents or branches building at once, this is where most of the wall-clock goes.

### Problem Statement

Observed with many concurrent worktrees of mid-sized workspaces:

- **Cold starts.** The first `cargo check` in a fresh worktree rebuilds every dependency, and build scripts and proc-macros compile fully even under `check`. Worktrees are short-lived, so most checks are cold.
- **Lock contention.** rust-analyzer's check-on-save, `cargo check`/`test` and `cargo nextest` in one worktree all take the exclusive lock on one target dir ("Blocking waiting for file lock on build directory"), which reads as a hang.
- **Disk.** Per-worktree `target/` dirs are never reclaimed. Cargo's automatic cache GC (stable since 1.88) only cleans `~/.cargo`, never `target/`. Hosts slowly fill with tens to hundreds of GB of stale build dirs.
- **No shared compile cache in the dev loop.** See #1889.

### Proposed Solution

All opt-in or zero-cost defaults:

1. **rust-analyzer in its own target dir.** Ship editor settings (`.vscode/settings.json`, plus a documented `rust-analyzer.toml`) with `"rust-analyzer.cargo.targetDir": true`, so RA never blocks the CLI.
2. **Warm-start new worktrees.** In `worktree-start`, copy-on-write clone a sibling worktree's build dir. `cp -c` on APFS and `cp --reflink=auto` on Btrfs/XFS are near-free, and cargo's fingerprints keep it correct. Fall back to nothing when reflinks aren't supported.
3. **Document `build.build-dir`.** `build-dir = "<scratch>/{workspace-path-hash}"` splits the intermediate-artifact churn from `target/` (final artifacts only). I verified it on stable cargo 1.96 with the template honoured and no `-Z` flag. It lets a host put build churn on dedicated scratch storage and GC one place.
4. **Reclaim.** A `just clean-stale` / worktree-clean hook (`cargo sweep`-style, or deep-mtime based: never delete a dir with recently modified files) plus a documented cron.
5. **Docs:** a short "Rust in many worktrees" page explaining why these are the defaults.

### Alternatives Considered

- A single shared `CARGO_TARGET_DIR` for all worktrees: serialises every build on one lock. Rejected.
- Pushing all builds through Nix (crane): good for CI and release, too slow for the edit→check loop (no incremental compilation).

### Impact

Rust consumers using worktrees. Editor settings and worktree recipes are managed files.

### Changelog Category

Added

