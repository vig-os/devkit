---
type: issue
state: open
created: 2026-11-08T14:37:16Z
updated: 2026-11-08T14:37:16Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2066
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-09T09:33:49.002Z
---

# [Issue 2066]: [[FEATURE] Rust pack: cross-target check of a crate subset (e.g. aarch64-apple-ios, x86_64-unknown-linux-gnu) in mkRustProject checks](https://github.com/vig-os/devkit/issues/2066)

Consumer: nerdmachines/quench (2026-11-08). Its framework crates must stay portable to macOS, Linux and `aarch64-apple-ios` (ADR 0001 rule 5), so it hand-rolled crane checks for that in its scaffold (quench PR #50). It is moving to `lib.mkRustProject` and needs this from devkit.

Ask: an `mkRustProject` option, e.g. `crossChecks = [ { target = "aarch64-apple-ios"; crates = [ ... ]; } { target = "x86_64-unknown-linux-gnu"; crates = [ ... ]; } ]`, producing one `cargo check --target <t> -p <crates>` derivation per entry. Requirements:
- shares the deps-only artifacts with the host checks;
- targets added to the toolchain from rust-toolchain.toml;
- documented limits:
  - check-only, no linking;
  - a Linux check does not catch Apple FFI declarations (core-foundation-sys compiles on Linux), so platform-crate bans belong in the layer check (#1957);
  - crates with build scripts targeting iOS need pure-Rust features (e.g. blake3 `pure`) or the iOS SDK, which CommandLineTools-only hosts lack.

quench carries a local extra check beside mkRustProject until this lands.
