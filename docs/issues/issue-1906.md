---
type: issue
state: open
created: 2026-10-21T00:04:07Z
updated: 2026-10-21T00:04:07Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1906
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-21T07:24:29.987Z
---

# [Issue 1906]: [setup-devkit-toolchain: NIX_CFLAGS_COMPILE / NIX_LDFLAGS not forwarded to later CI steps (-sys crates build locally, fail in CI)](https://github.com/vig-os/devkit/issues/1906)

Observed while bootstrapping a Rust consumer (devkit 1.18.0, direnv mode, solo profile).

`.github/actions/setup-devkit-toolchain/action.yml` (~line 336) exports PATH, `PKG_CONFIG_PATH` and `LIBCLANG_PATH` from the dev shell to $GITHUB_ENV, but not the Nix compiler-wrapper variables (`NIX_CFLAGS_COMPILE`, `NIX_LDFLAGS`, and `NIX_CC` for completeness). A `-sys` crate that finds a C library through the wrapper's include/lib flags rather than pkg-config (for example hdf5-sys and bindgen consumers) builds inside `nix develop` but fails in later CI steps.

Ask: forward the dev shell's `NIX_CFLAGS_COMPILE`/`NIX_LDFLAGS`, or run consumer steps inside `nix develop -c`, and document which variables the action exports.
Found by review of MorePET/visionx-rs#11.
