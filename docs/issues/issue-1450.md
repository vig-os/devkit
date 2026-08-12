---
type: issue
state: open
created: 2026-08-12T09:33:35Z
updated: 2026-08-12T09:33:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1450
comments: 0
labels: feature, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:39.767Z
---

# [Issue 1450]: [Rust pack: four consumer-hardening fixes from the second consumer](https://github.com/vig-os/devkit/issues/1450)

Four fixes to `lib.mkRustProject`, all found by adopting #1429 on a second consumer (`gerchowl/squelch` — a single-crate, no-binary, heavily feature-gated library, so a different shape from filesender). Full adoption report: vig-os/devkit#1429 (comment).

Each is small and independent. Two are guards against a silent or opaque failure; two close a coverage gap the pack currently opens without saying so.

## 1. `mkRustProject` should refuse a `pkgs` without `overlays.default`

`rust.devShell` cannot evaluate unless the consumer's nixpkgs carries `devkit.overlays.default`, because `mkProjectShell` → `nix/devtools.nix:36` references `vig-utils`. Without it:

```
error: undefined variable 'vig-utils'
       at .../nix/devtools.nix:36:21
```

— an error inside devkit, naming a variable the consumer has never seen, from a file they did not open.

The reason this is a guard and not a docs fix: **`checks` and `packages` evaluate fine without the overlay**, because they never touch `mkProjectShell`. The result is a repo with a green `nix flake check` and a broken `nix develop`. That is the same silent split the pack exists to close, one layer up.

`pkgs ? vig-utils` is a one-line test. The message should say what to add and why, in mkRustProject's own voice — the `toolchainHash` error is the model.

## 2. `mkRustProject` should say what a missing `Cargo.lock` means

A flake's `src = ./.` is the git tree, so a repo that gitignores `Cargo.lock` — the long-standing library convention, and what `cargo new --lib` emitted for years — hands crane a source with no lockfile. Five of six derivations then fail at eval with crane's `unable to find Cargo.lock`.

crane's own message is good and names `git add -N Cargo.lock`. Two things the pack should add:

- **Two of crane's three suggested remedies are unreachable.** There is no `cargoVendorDir` argument, and `crateOverrides` only reaches `buildPackage` — not `buildDepsOnly`, `cargoClippy`, `cargoNextest` or `cargoDoc`. A consumer who cannot commit a lock has to abandon the function and rebuild it from the exposed `craneLib`/`commonArgs`.
- **`fmt` passes regardless**, since it takes only `src`. A consumer who builds one check first sees green.

A `builtins.pathExists (src + "/Cargo.lock")` guard naming the library case turns "the pack doesn't work" into "stage your lockfile".

## 3. Nothing runs doctests — #1400 said it would

The stage table in #1400 assigns pre-push `nextest` **+ `cargo test --doc`**. #1429 ships `cargoDoc` (rustdoc lints under `-D warnings`) but nothing executes doctests, and nextest cannot by design.

For a consumer whose doctests currently run under `cargo test`, adopting the pack **removes them from CI silently**. squelch has three, including the macro example that is its main API surface.

`crane` already ships `lib/cargoDocTest.nix`; this should be one more `lib.optionalAttrs` block beside `doc`.

## 4. No supported way to build with non-default features

The checks build default features only. On squelch:

| | tests run |
|---|---|
| `cargo test --all-features` (the repo's real suite) | 59 |
| the pack's `nextest` | 55 |

The four missing tests cover three optional features, and more importantly **clippy never compiles that code at all** — so a feature-gated crate gets less linting from the pack than from a bare `cargo clippy --all-features`.

`clippyExtraArgs` exists, but nothing reaches `buildDepsOnly` / `nextest` / `doc` / the package builds.

The seam that works today is `buildEnv = { cargoExtraArgs = "--all-features"; }`, because `buildEnv` is merged verbatim into `commonArgs`. That works (verified: 59 tests), but `buildEnv` is documented as "For CMAKE_*, PKG_CONFIG_PATH, etc." — it is a general crane override wearing an env-var name, and something that reads its docstring will eventually narrow it. Either promote a real `features` / `cargoExtraArgs` argument, or document `buildEnv` as what it is.

Note a real interaction: a top-level `cargoExtraArgs` would collide with `buildCrate`'s `cargoExtraArgs = "-p ${name}"` on a workspace. Single-crate consumers do not hit it; the fix needs to compose the two rather than overwrite.

---

Refs #1400, #1429.

