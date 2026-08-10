---
type: issue
state: closed
created: 2026-08-07T08:22:06Z
updated: 2026-08-07T09:53:30Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1351
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:05.106Z
---

# [Issue 1351]: [fix(action): setup-devkit-toolchain GITHUB_PATH export reverses dev-shell PATH order](https://github.com/vig-os/devkit/issues/1351)

## Problem

`setup-devkit-toolchain` (direnv mode) extracts the consumer dev-shell `$PATH`, filters the `/nix/store` bin dirs, and writes them line-by-line to `GITHUB_PATH`. GitHub prepends each line, so the resulting runner PATH has the dev-shell's entries in **reverse priority order**.

This is invisible when one tool = one store path, which is why every Python/TS consumer has been green. It breaks the moment the shell carries wrapped/unwrapped pairs: a Rust consumer's shell has `gcc-wrapper` before raw `gcc` (and `binutils-wrapper` before raw `binutils`); reversed, the **raw compiler shadows the wrapper**, and any C build (cc-rs, cmake) fails with the classic unwrapped-gcc signature:

```
ld.bfd: cannot find Scrt1.o: No such file or directory
ld.bfd: cannot find -lc: No such file or directory
```

First live hit: vig-os/h5v#2 (`hdf5-metno-src` vendored HDF5 cmake build), CI run 31160809242. Locally the same build is green because `nix develop` preserves order.

## Expected

Preserve dev-shell PATH priority on the runner — e.g. write the store bin dirs to `GITHUB_PATH` in reverse (so GitHub's per-line prepend restores the original order), or export a single joined `PATH` line.

## Aggravating factor

stdenv sets `CC=gcc` / `CXX=g++` as bare names in the dev-shell env, and the #1180 shellHook-env forward ships them to `GITHUB_ENV` — so even tools that honor `CC` resolve it through the reversed PATH.

## Workaround (consumer-side, applied in vig-os/h5v#2)

Export absolute wrapped-toolchain paths from the flake `shellHook` (forwarded to CI by #1180):

```nix
shellHook = ''
  export CC=${pkgs.stdenv.cc}/bin/cc
  export CXX=${pkgs.stdenv.cc}/bin/c++
'';
```

Verified by rebuilding the failing crate under a deliberately reversed store PATH.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 09:53 AM_

Fixed on dev by PR #1356: the direnv-mode setup-devkit-toolchain now writes the dev-shell store bin dirs to GITHUB_PATH in reverse order, so the runner's per-line prepend rebuilds the dev-shell PATH priority verbatim — wrapped toolchains (gcc-wrapper/binutils-wrapper) keep precedence over the raw compilers on CI. Ships with the next devkit release; the consumer-side CC/CXX shellHook workaround in vig-os/h5v#2 can be dropped after the upgrade.

