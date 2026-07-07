---
rfc: ADR-capability-modules
date: 2026-07-07
title: Opt-in capability modules on mkProjectShell
status: accepted
authors:
  - Carlos Vigo (c-vigo)
---

# Design note: capability modules for `mkProjectShell`

**Decision (TL;DR):** `mkProjectShell` gains an opt-in
`modules = [ "<name>" … ]` string list. A module is a curated, tested,
Renovate-tracked contribution of **packages, environment variables, and
shellHook fragments — nothing else in v1** — defined once in `nix/modules/` and
composed onto the existing plain-`mkShell` builder. The zero-module path is
**byte-identical** to today's dev-shell (same derivation hash), the published
image stays base-only, and `native` is the only module that ships now; further
modules are gated on a concrete consumer ask. This is the modular layer
[ADR-nix-devenv-strategy](ADR-nix-devenv-strategy.md) anticipated — it reopens
none of that ADR's builder decisions (plain `pkgs.mkShell`, no
`cachix/devenv` / `numtide/devshell`, services via process-compose).

## Problem

0.4.0 downstream validation (#639/#879/#882) settled *where* native toolchains
come from — the project flake, direnv-mode — but every consumer hand-rolls the
same `extraPackages` content. There is no curated, tested definition of a
capability, and "no C++ in my pure-Python repo" is guaranteed only by omission.

## v1 module contract

A module is a function `pkgs -> contribution`, where the contribution is an
attrset with exactly these (all optional) fields:

| Field | Type | Composed how |
|-------|------|--------------|
| `packages` | list of derivations | appended to the shell's `packages`, **after** `extraPackages` |
| `env` | attrset of strings | merged into the `mkShell` attrset; the builder's own env pins win |
| `shellHook` | string | concatenated (newline-terminated) **before** the consumer `shellHook` |

Explicitly **not** in v1:

- **Hooks contribution** (e.g. `native` adding `clang-format` to the #883
  consumer hook set) — open design question, recorded here for #883's wave;
  the seam keeps the `mkProjectShell` diff region small so #883's `hooks`
  argument lands beside `modules` without conflict.
- **Per-module option attrsets** (e.g. Geant4 dataset selection) — see
  migration path below.

## Composition rules

- **Consumer surface:** `modules = [ "native" ]` — names, not attrsets.
  Unknown names `throw` at eval time listing the available modules.
- **Order & precedence:**
  - `packages = devTools ++ [ python ] ++ extraPackages ++ modulePackages` —
    earlier entries win PATH lookup, so `extraPackages` (the per-repo escape
    hatch, unchanged) overrides a module, and the toolchain SSoT overrides
    both. Module order in the list is the tiebreak among modules.
  - `env`: modules merge left-to-right (later module wins); the builder's
    reserved variables (`UV_PYTHON`, `UV_PYTHON_DOWNLOADS`,
    `UV_PYTHON_DOWNLOADS_JSON_URL`, `BATS_LIB_PATH`) always win — a module
    cannot break the Python bootstrap.
  - `shellHook`: builder hooks (LD_LIBRARY_PATH guard, nvim isolation), then
    module hooks in list order, then the consumer `shellHook` — the consumer
    keeps the last word.
- **Zero-module invariant:** `modules = [ ]` (the default) contributes an
  empty list, an empty attrset, and an empty string — the resulting
  derivation is byte-identical to the pre-#884 shell, asserted by comparing
  `devShells.<system>.default.drvPath` and by the unchanged parity suite
  (`tests/test_flake_devshell.py`). The image continues to bake `devTools`
  only; modules are a direnv-mode/devshell feature.

## Shipped and candidate modules

- **`native` (ships now):** `stdenv.cc`, `cmake`, `gnumake`, `pkg-config`,
  plus `CC=cc` / `CXX=c++` exports. The generic sdist-building capability and
  #879's long-term answer: the image-side sysconfig sanitize (0.4.1) makes
  build backends do PATH discovery with generic names; this module provides
  the PATH (demonstrated need: hyrr/pycatima, #639).
- **Ask-gated candidates (named, not shipped — YAGNI):** `geant4`
  (fast-follow once an EXOMA/EXOPET repo asks), `rust`, `fortran`/`f2py`,
  `root`. Each ships with its own devshell smoke check (e.g. `geant4-config`
  resolves) the release it lands.

## Migration path to per-module options

When a module needs configuration (e.g. Geant4 datasets), `modules` also
accepts an attrset entry `{ name = "geant4"; datasets = [ … ]; }` alongside
plain strings — additive, no break for the string form. Not built until the
first module needs it.

## Testing

- Per-module flake check `checks.<system>.module-<name>` (generated from the
  module registry, so a new module cannot ship without its check) builds the
  module's devshell on every default system, including both Linux systems.
- `tests/test_flake_modules.py` smoke-tests the `native` module end-to-end: a
  trivial setuptools C-extension fixture builds as an sdist and installs
  (compiles) with `uv` inside the module devshell.

## Coordination

- **#885 (`DEVKIT_MODULES` in `.vig-os`):** the scaffold-level declaration
  maps onto this flake-level contract — one name list, two layers; this issue
  is the foundation, #885 the plumbing.
- **#883 (consumer hooks):** lands `hooks` as a sibling argument; module
  hooks-contribution is the recorded open question above.

## References

`flake.nix` (`mkProjectShell`, `nix/modules/`),
[MIGRATION.md — native-build contract](../MIGRATION.md#the-native-build-contract),
[docs/NIX.md](../NIX.md), issues #884 (this), #882, #879, #854, #639, #883,
#885; sibling ADRs [ADR-nix-devenv-strategy](ADR-nix-devenv-strategy.md),
[ADR-home-environment-modules](ADR-home-environment-modules.md).
