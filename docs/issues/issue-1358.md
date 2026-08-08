---
type: issue
state: closed
created: 2026-08-07T10:15:59Z
updated: 2026-08-07T12:11:30Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1358
comments: 1
labels: bug
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:03.473Z
---

# [Issue 1358]: [fix(action): shellHook env forward still leaks Nix-host state (PYTHONPATH store paths, stdenv machinery, IN_NIX_SHELL)](https://github.com/vig-os/devkit/issues/1358)

## Problem

The #1353 denylist audit of the `setup-devkit-toolchain` shellHook env forward (#1180) surfaced pre-existing leaks that are out of that issue's scope but the same failure family — dev-shell/Nix-host state shipped to `GITHUB_ENV`:

1. **`PYTHONPATH` with store components.** Because `python` is in the dev-shell `packages`, the nixpkgs python setup hook exports `PYTHONPATH=/nix/store/…-python3.14-vig-utils-…/lib/python3.14/site-packages:…`. Forwarded to CI, this puts Nix-built `cp314` site-packages on the `sys.path` of the downloaded manylinux venv python — same ABI tag, importable, exactly the mixed-loader shape behind #1353's `ImportError: libstdc++.so.6`. A blanket deny is wrong (a consumer shellHook exporting `PYTHONPATH=$PWD/src` is a legitimate #1180 use case); needs a narrower rule, e.g. strip `/nix/store` components from path-like values.
2. **stdenv machinery the current denylist misses**: `_PYTHON_HOST_PLATFORM`, `_PYTHON_SYSCONFIGDATA_NAME`, `DETERMINISTIC_BUILD`, `doCheck`, `doInstallCheck` (`dont*` is caught but `do*` is not), `CONFIG_SHELL`, and the binutils/toolchain names `AR AS CC CXX LD NM OBJCOPY OBJDUMP RANLIB READELF SIZE STRINGS STRIP`. Benign on an FHS runner in practice, but the same family as entries already denied; `CC=gcc`/`CXX=g++` was already named an aggravating factor in #1351.
3. **`IN_NIX_SHELL=impure`** — makes every subsequent CI step claim to run inside a nix shell.

## Related latent gap (may deserve its own issue at triage)

A Python direnv consumer on a **NixOS self-hosted runner** is broken by design of the PATH filter: the `pyproject.toml`-gated exclusion (#1028) removes the bare Nix CPython unconditionally, and after #1353 `uv` downloads a managed CPython that NixOS cannot execute (before #1353, the forwarded `UV_PYTHON` masked this). No current consumer matches the combination (the only NixOS self-hosted runner consumer has no `pyproject.toml`), but the filter should become NixOS-aware (e.g. keep the Nix CPython when `/etc/NIXOS` exists on the runner).

## Method that found these

Diff of `nix develop -c env -0` against a scrubbed ambient env, replayed through the action's denylist — see #1353 / PR #1357.

Refs: #1353, #1351, #1180
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 11:12 AM_

Fixed on dev by PR #1361: PYTHONPATH is now store-stripped in the forward loop (consumer components like $PWD/src survive verbatim; the var is skipped when only store paths remain), and the denylist gains IN_NIX_SHELL, _PYTHON_HOST_PLATFORM, _PYTHON_SYSCONFIGDATA_NAME, DETERMINISTIC_BUILD, CONFIG_SHELL, do[A-Z]*, and the stdenv cc/binutils hook names AR–STRIP. Two accepted collisions documented in the changelog: the pre-#1351 h5v CC/CXX workaround (superseded) and native.nix's CC=cc/CXX=c++ exports (PATH discovery still applies on CI via GITHUB_PATH). The NixOS-self-hosted PATH-filter gap is tracked separately in #1360. Ships with the next devkit release.

