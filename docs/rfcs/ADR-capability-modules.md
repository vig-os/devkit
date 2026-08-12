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
- **`rust` (ships now):** the Rust language pack — a toolchain and curated
  cargo tooling on the dev-shell PATH, and a mandatory `checks` option that
  makes the bare `modules = [ "rust" ]` form a loud eval-time refusal (see the
  #1427 decision below). Shipped on gerchowl/filesender's ask (#1400). The
  generated `checks.<system>.module-rust` cannot instantiate the module the
  same way it does `native`/`node`/`docs` (the bare name throws by design), so
  a per-name override in `nix/modules/check-entries.nix` supplies the
  toolchain-only opt-out form (see the internal-plumbing subsection below).
  The composed entry point for a Rust consumer is `lib.mkRustProject`.
- **Ask-gated candidates (named, not shipped — YAGNI):** `geant4`
  (fast-follow once an EXOMA/EXOPET repo asks), `fortran`/`f2py`, `root`.
  Each ships with its own devshell smoke check (e.g. `geant4-config` resolves)
  the release it lands.

## Decision: `checks` stays out of the v1 contract (#1427)

The Rust pack (#1400) forced the question the ADR punted: can a capability
module contribute `checks.<system>.*`? The answer is no — the contract is not
extended, and the Rust pack composes ABOVE it instead.

**Why the v1 contract does not extend to `checks`.** `packages`, `env` and
`shellHook` fold monoidally into one derivation — the dev shell — and that
folding is exactly what `mkProjectShell` does. `checks` is not that shape: it
is a namespaced map of independent peer derivations on a different lifecycle
(`nix flake check`, not `nix develop`), and building them needs the consumer's
source tree — project shape a module never sees. The decisive test: a `checks`
field could be added to the shell-composition contract WITHOUT touching shell
composition at all — the folding, the ordering, the reserved-env rules would
be untouched. If a field can be added to a contract without touching what that
contract composes, it is not part of that contract.

**What ships instead.** `lib.mkRustProject` is a composed entry point ABOVE
`mkProjectShell`. It wires the dev shell (via `mkProjectShell` with the `rust`
module) AND the checks AND the packages from ONE call, returning them
together. Crucially it is one call: there is no second function a consumer can
forget to invoke, which was the whole objection to shipping the checks
separately. The `rust` module itself keeps the v1 contract and gains a
mandatory `checks` option with no default — a hand-written
`modules = [ "rust" ]` fails at EVAL with a message that names the fix
(`mkRustProject`) and the deliberate opt-out
(`{ name = "rust"; checks = "none"; }`). Silence was the failure mode; that
silence is what is removed.

**Honest limitation.** Flake outputs are consumer-assigned by construction:
`devShells.default = …`, `checks = …`, `packages = …` are the consumer's
writes into their own flake, and NO contract change anywhere in devkit —
including a hypothetical `checks` field on the module contract — could make
wiring structurally impossible. What the chosen shape buys is real but
bounded: one call instead of two, `checks` arriving visibly beside `devShell`
so dropping it is a visible omission rather than an unknown-unknown, and a
loud eval-time refusal on the remaining hand-edited path.

**When to revisit.** Extend the contract when a SECOND capability module
independently needs to contribute checks — demonstrated by a non-Rust
consumer, not argued from one repo. One data point is a language pack; two is
a pattern the contract should absorb.

**Options considered and rejected.**

- **(B) Extend the v1 contract with a `checks` field.** Rejected: the shape
  is Rust-shaped, dead weight for `native`/`node`/`docs` which have no checks
  to contribute, and a contract seam paid for by every module and every
  consumer forever on the evidence of one repo. The decisive-test criterion
  above formalises the rejection: a field a contract can accept without
  touching what it composes is not part of it.
- **(C) Template-only Rust starter (no module, no `mkRustProject`).**
  Rejected: templates cover the greenfield path — one project bootstrap — and
  nothing else. Hand-edits, copy-paste between repos, existing repos
  retrofitted, agent-generated flakes: none of them go through
  `nix flake init`, and the failure mode the pack exists to prevent lives in
  precisely those cases.

### Internal plumbing: `nix/modules/check-entries.nix`

Not consumer surface. The flake generates `checks.<system>.module-<name>` for
every entry in the registry (`nix/modules/default.nix`) so a module cannot
ship without its check. The generator's default instantiation is the plain
name string — the same thing a consumer writes for a module that needs no
configuration. A module whose options are MANDATORY cannot be instantiated
that way: the bare name throws by design. `nix/modules/check-entries.nix` is
the generator's per-name override — a name → `modules` entry override,
consulted only for the names present in it. Currently one entry: `rust` maps
to `{ name = "rust"; checks = "none"; }`, the sanctioned toolchain-only form
(the smoke check builds the devshell to prove the module evaluates and its
packages resolve; deeper end-to-end coverage lives in
`tests/test_flake_modules.py`). Keep the file small and keep each entry
justified — an entry is a statement that the module's zero-option form is
deliberately unusable, not that the check was inconvenient to write.

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

`flake.nix` (`mkProjectShell`, `lib.mkRustProject`, `nix/modules/`,
`nix/modules/check-entries.nix`, `nix/mk-rust-project.nix`),
[MIGRATION.md — native-build contract](../MIGRATION.md#the-native-build-contract),
[docs/NIX.md](../NIX.md), issues #884 (this), #882, #879, #854, #639, #883,
#885, #1400 (Rust pack ask), #1427 (checks-in-contract decision); sibling ADRs
[ADR-nix-devenv-strategy](ADR-nix-devenv-strategy.md),
[ADR-home-environment-modules](ADR-home-environment-modules.md).
