---
type: issue
state: open
created: 2026-10-14T19:40:18Z
updated: 2026-10-14T19:40:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1886
comments: 0
labels: bug, priority:medium, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:46.877Z
---

# [Issue 1886]: [[BUG] Rust dev shell's mold RUSTFLAGS export discards repo .cargo/config rustflags and splits shell/IDE fingerprints](https://github.com/vig-os/devkit/issues/1886)

### Description

The rust module's Linux shellHook exports mold through `RUSTFLAGS` (`nix/modules/rust.nix`, on `dev`):

```nix
# Deliberately additive to RUSTFLAGS rather than assigning it, so a repo's
# own .cargo/config.toml or a caller's export is not silently discarded.
shellHook = lib.optionalString useMold ''
  export RUSTFLAGS="''${RUSTFLAGS:+$RUSTFLAGS }-C link-arg=-fuse-ld=mold"
'';
```

The comment's guarantee doesn't hold. Cargo reads **exactly one** source of extra rustc flags and uses the first one set, in this order: `CARGO_ENCODED_RUSTFLAGS`, then `RUSTFLAGS`, then all matching `target.<triple>.rustflags` / `target.<cfg>.rustflags`, then `build.rustflags` (see the [cargo config reference, `build.rustflags`](https://doc.rust-lang.org/cargo/reference/config.html#buildrustflags)). As soon as the env var is set, every `rustflags` in the repo's `.cargo/config.toml` (and in `~/.cargo/config.toml`) is ignored. Only a caller's *exported* `RUSTFLAGS` is preserved.

### Steps to Reproduce

1. In a devkit Rust repo on Linux, add `.cargo/config.toml` with `[build] rustflags = ["--cfg", "from_config"]`.
2. Enter the dev shell (`direnv` / `nix develop`) and run `cargo build -v`.
3. The rustc command line contains `-C link-arg=-fuse-ld=mold` but not `--cfg from_config`.

### Expected Behavior

Repo-level and user-level cargo config rustflags still apply inside the dev shell, as the comment promises.

### Actual Behavior

They're silently dropped. Second effect: tools started outside the shell (an IDE's rust-analyzer, a cargo spawned by a GUI or an agent harness without direnv) see different flags than the shell does. Both write to the same `target/`, so every switch between them invalidates fingerprints and triggers a full rebuild.

### Environment

devkit `dev` (rust module, `useMold` on Linux). The precedence itself is platform-independent. Verified with cargo 1.96: with `build.rustflags = ["--cfg", "from_config"]` in `.cargo/config.toml`, `cargo build -v` passes `--cfg from_config`. With any `RUSTFLAGS` exported, that flag disappears from the rustc command line.

### Possible Solution

Pick one:

1. **Drop the override on x86_64 Linux.** `rust-lld` is rustc's default linker for `x86_64-unknown-linux-gnu` since Rust 1.90 ([release notes](https://blog.rust-lang.org/2025/09/18/Rust-1.90.0/)), which removes most of mold's advantage there. Keep mold opt-in only.
2. **Move the linker choice into cargo config.** Managed scaffold, merged rather than overwritten: `[target.x86_64-unknown-linux-gnu] rustflags = ["-C", "link-arg=-fuse-ld=mold"]`. It then composes with the repo's config and is identical inside and outside the shell.
3. If an env var is kept, use `CARGO_TARGET_<TRIPLE>_LINKER` with a mold wrapper (a `linker`, not `rustflags`), so rustflags precedence isn't touched.

In every case, fix the comment and add a test that asserts a repo `build.rustflags` survives the dev shell.

### Changelog Category

Fixed

