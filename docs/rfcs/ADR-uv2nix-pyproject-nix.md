---
rfc: ADR-uv2nix-pyproject-nix
date: 2026-07-01
title: Scope uv2nix/pyproject-nix against the FHS/manylinux scar tissue
status: accepted
authors:
  - Carlos Vigo (c-vigo)
---

# ADR: uv2nix / pyproject-nix vs the FHS/manylinux scar tissue

**Decision (TL;DR):** **Defer adoption.** uv2nix/pyproject-nix genuinely
*eliminate* the manylinux-wheel loader problem — but only for the wheels **inside
the project venv they build**, which today is a problem this repo does not have
(the baked `pythonEnv` deps are all pure Python). The scar tissue #775 actually
targets lives on two surfaces uv2nix **cannot reach** — **pre-commit's own hook
environments** and the **image's runtime substrate for downstream/consumer
wheels** — plus two non-Python items. So adopting uv2nix would *leave* the bulk of
the scar tissue in place while adding 3 flake inputs, an override overlay, and
regressing the live `uv` dev-loop. Its one genuine win here is tidying the two
hand-rolled `buildPythonPackage` derivations behind `pythonEnv`. Net: not worth it
now. Revisit only if `pythonEnv` grows native-wheel deps or we bake a fully
hermetic project venv into the image (see *Reconsider if*).

## Problem Statement

The flake's Python handling carries FHS/manylinux "scar tissue": a cluster of
loader symlinks, `LD_LIBRARY_PATH` exports, interpreter pins and venv-scaffold
rewrites whose shared root cause is **uv fetching / installing generic-ELF
manylinux wheels that a no-FHS Nix store cannot run natively**. The issue (#775)
asks whether adopting **uv2nix** + **pyproject-nix** — which build a hermetic venv
directly from `pyproject.toml` + `uv.lock` — would **eliminate** this scar tissue,
or merely **relocate** it, and to capture the decision either way.

### The scar tissue, enumerated (`flake.nix` @ `dev`, ae50df28)

Grouped by the surface it lives on and the root-cause issue cited inline.

**(A) Dev-shell interpreter pin — avoid uv downloading a generic CPython (#683)**

- `python = pkgs.python314` — `flake.nix:178`
- `UV_PYTHON = "${python}/bin/python3.14"` — `flake.nix:242`
- `UV_PYTHON_DOWNLOADS = "never"` — `flake.nix:243`
- `uvPythonDownloadsJsonUrl` (`flake.nix:167`) + `UV_PYTHON_DOWNLOADS_JSON_URL`
  (`flake.nix:254`) — the CI escape hatch: an FHS runner *does* download a managed
  CPython because a store interpreter can't load pre-commit's manylinux C
  extensions there.
- Root cause: on NixOS, `uv sync` downloads a generic dynamically-linked CPython
  that cannot execute (no FHS `ld-linux`) — `just init` aborted (#683).

**(B) Dev-shell `libstdc++` on the loader path — for pre-commit C-extension hooks (#698, #703)**

- `ldLibraryPath = "${pkgs.stdenv.cc.cc.lib}/lib"` — `flake.nix:190`
- `ldLibraryPathHook`, NixOS-gated on `/etc/NIXOS` — `flake.nix:202-206`
- Root cause: the `pymarkdown` pre-commit hook runs from pre-commit's **own**
  manylinux-wheel env, whose dep `pyjson5` (a C extension) needs `libstdc++.so.6`
  off the loader path on NixOS (#698); the export is NixOS-gated to avoid an ABI
  leak into FHS-host binaries (#703).

**(C) Image runtime substrate — for runtime-installed manylinux wheels (#735, #736)**

- `manylinuxLibPath` (`stdenv.cc.cc.lib` + `zlib`) — `flake.nix:463-466`
- Arch-specific FHS loader `fhsLoaderName`/`fhsLoaderDir` — `flake.nix:472-474`,
  symlinked at `flake.nix:593-595`
- `.venv` scaffold + build-time store-path rewrite — `flake.nix:531-544` (#735)
- `LD_LIBRARY_PATH=${manylinuxLibPath}` in `config.Env` — `flake.nix:673` (#736)
- `UV_PYTHON_DOWNLOADS=never` / `UV_PYTHON` in image env — `flake.nix:686-687`
- Root cause: a bare Nix layered image lacks the FHS loader every manylinux wheel
  hardcodes as `PT_INTERP`, and lacks the C++/z runtime the wheels' C extensions
  `dlopen`; both are needed so **runtime-installed** wheels (pre-commit hooks, and
  the consumer's `just sync`/`uv sync` populating `.venv` at post-create) work
  inside the container (#736).

**(D) Hand-rolled `pythonEnv` derivations (the one uv2nix genuinely owns)**

- `vigUtils` = `python.pkgs.buildPythonPackage { … }` — `flake.nix:274-284`
- `pipLicenses` = wheel `buildPythonPackage` (avoids a setuptools>=82 backend) —
  `flake.nix:290-300`
- `pythonEnv = python.withPackages [ vigUtils pipLicenses ]` — `flake.nix:305-308`

**(E) Non-Python items the issue bundles in but uv2nix cannot touch**

- npm global-prefix shim (`/usr/local`, `NPM_CONFIG_PREFIX`) — `flake.nix:556`,
  `flake.nix:685` (#728) — a Node concern, unrelated to Python wheels.
- `docker`→`podman` wrapper — `flake.nix:568-572` (#740) — a container-CLI
  concern, unrelated to Python wheels.

The current design and its history are documented in
[`docs/NIX.md`](../NIX.md) (§"uv and the project interpreter", §"libstdc++ for
C-extension pre-commit hooks") and the issue notes for #683/#697/#698/#703.

## How uv2nix / pyproject-nix actually work (the mechanism this decision turns on)

- **pyproject-nix** provides Nix builders that turn a Python distribution
  (`sdist` or `wheel`) into a store derivation, plus the venv/override
  infrastructure. **uv2nix** parses `uv.lock` (`loadWorkspace` /
  `mkPyprojectOverlay`) into a package overlay consumed by those builders;
  `mkVirtualEnv` links the resolved set into one venv derivation in the store.
- `sourcePreference` (no default — you must choose) selects `"wheel"` or
  `"sdist"`:
  - **`sourcePreference = "wheel"`** installs prebuilt manylinux wheels and runs
    **`autoPatchelfHook` automatically on every wheel**, rewriting the ELF
    interpreter (`PT_INTERP`) and `RPATH` to Nix store paths at build time. The
    standard manylinux baseline libs (glibc, libstdc++, libz, …) are wired in
    automatically. So a wheel's C-extension `.so` runs on a no-FHS store **with no
    runtime `LD_LIBRARY_PATH`** — a real *elimination*, not a shim relocation. A
    per-package override is needed **only** when a wheel expects an *external*
    system library outside that baseline (e.g. `numba`→`tbb`); then
    `autoPatchelf` **fails the build** (fail-fast, not a silent runtime crash) and
    you add the lib via `buildInputs` in a `pyprojectOverrides` entry.
  - **`sourcePreference = "sdist"`** builds from source in the Nix sandbox; since
    `uv.lock` does not record build-system deps, each finicky backend needs
    `nativeBuildInputs`/`resolveBuildSystem` overrides. Avoid unless a wheel is
    unavailable.
- **Cost surface:** three direct flake inputs (`pyproject-nix`, `uv2nix`,
  `build-system-pkgs`), each `follows`-pinnable to our `nixpkgs`; `flake-parts` is
  **not** required. There is **no bundled overrides collection** (a deliberate
  anti-poetry2nix-burnout choice), so with `wheel` preference typical projects
  need zero-to-few `overrideAttrs` stanzas.
- The venv derivation is a hermetic, content-addressed closure with no runtime
  `uv`/network step — **suitable to drop into `dockerTools.buildLayeredImage` with
  a stable digest.** Editable/path deps are supported via a *separate*
  `mkEditablePyprojectOverlay` used in the dev shell, not baked into the closure.

**Crucially for this repo:** uv2nix manages **only** the packages in *this repo's*
`uv.lock`. It does **not** manage (a) pre-commit's hook environments — pre-commit
provisions its own venvs at runtime from `rev:`-pinned PyPI hooks, and those
packages (`pyjson5`, etc.) are not in our `uv.lock` (upstream confirms this is out
of scope) — nor (b) a *consumer* repo's dependencies, since the devcontainer is a
**base image** built before any consumer's `pyproject.toml`/`uv.lock` exists.

Our own dependency set is favourable but also *undemanding*: the runtime
`pythonEnv` deps (`vig-utils` → `rich`, `pip-licenses` → `prettytable`) are all
**pure Python**, so uv2nix would face **no manylinux wheel at all** in the thing
it would build here today. The heavier C-extension deps in `uv.lock` (`bcrypt`,
`pyyaml`, `coverage`, `markupsafe`, `wrapt`, `charset-normalizer`) are dev/test-
only, each ship an `sdist`, and are **not** in the baked `pythonEnv` — so they are
not the thing the scar tissue exists for.

## Options Considered

### Option A — Status quo (keep the explicit shims)

- **Pros:** Works today on NixOS and FHS hosts and inside the image; each shim is
  small, load-bearing, and heavily commented with its root-cause issue; the image
  digest is reproducible; the dev-loop stays live `uv` (fast `uv add`/editable).
  No new inputs, no override overlay.
- **Cons:** The scar tissue is real cognitive load — several `LD_LIBRARY_PATH` /
  loader / interpreter-pin sites to understand and keep coherent across dev-shell,
  CI and image.
- **Decision:** The baseline the other options must beat.

### Option B — Adopt uv2nix/pyproject-nix (full)

Replace `uv sync` / `pythonEnv` with a uv2nix `mkVirtualEnv` from `uv.lock`,
dev-shell and image.

- **Pros:** `pythonEnv` becomes a real hermetic venv resolved from the lockfile
  rather than two hand-rolled `buildPythonPackage` derivations (eliminates item
  **D**). If `pythonEnv` ever gained a native wheel, that wheel's ELF/RPATH would
  be autoPatchelf'd automatically. The venv closure is reproducible for the image.
- **Cons:**
  - Does **not** touch **B** (pre-commit's own hook env) or **C** (runtime
    substrate for pre-commit hooks + *consumer* wheels) — both outside uv2nix's
    scope. The `LD_LIBRARY_PATH` and FHS loader must stay for exactly those.
  - Adds **3 flake inputs** + a `pyprojectOverrides` overlay, enlarging the
    lock/Renovate surface — against the "smaller closure / fewer inputs" posture
    (`docs/NIX.md`).
  - **Regresses the dev-loop:** the venv becomes a Nix derivation; live
    `uv add` / editable iteration (`just sync`) then relies on the separate
    editable overlay + keeping `uv` anyway, so you carry *both* mechanisms.
- **Decision:** Rejected now — high cost, and it leaves the dominant scar tissue
  (B, C) untouched because that scar tissue is architecturally outside what a
  project-venv builder can see.

### Option C — Partial adoption

- **C1 — dev-shell project venv only:** build the *project* venv with uv2nix
  instead of `uv sync`. Would eliminate #683's download in the dev-shell — but
  #683 is **already** fixed with a 2-line `UV_PYTHON` pin (item **A**), and this
  breaks the live editable dev-loop. Poor trade.
- **C2 — image `pythonEnv` only:** build just `pythonEnv` (item **D**) via uv2nix.
  This is the *only* place uv2nix cleanly helps. But it swaps ~25 lines of
  well-understood hand-rolled derivations for 3 flake inputs + an override overlay,
  while `pip-licenses`' wheel-backend workaround likely still needs a bespoke
  override. Marginal today, and it leaves **A/B/C/E** untouched.
- **Decision:** C2 is the least-bad adoption path but still net-negative now; hold
  it in reserve for the *Reconsider if* triggers.

## Eliminate vs Relocate vs Leave — per scar-tissue item

| Item | Scar tissue | uv2nix verdict |
|------|-------------|----------------|
| **A** | Dev-shell `UV_PYTHON`/`…DOWNLOADS=never` interpreter pin (#683) | **Eliminate (for the project venv)** — a Nix-built venv is never `uv`-downloaded; but the fix is already a 2-line pin, and CI's `…JSON_URL` path (for an FHS runner's *pre-commit* wheels) stays regardless. |
| **B** | Dev-shell `libstdc++` `LD_LIBRARY_PATH`, NixOS-gated (#698, #703) | **Leave** — pre-commit manages its **own** hook env; `pyjson5` is not in `uv.lock`. uv2nix has zero visibility into it (upstream-confirmed out of scope). |
| **C** | Image FHS loader + `LD_LIBRARY_PATH` + `.venv` scaffold (#735, #736) | **Leave** — this substrate serves **runtime-installed** wheels: pre-commit hooks and the **consumer's** `uv sync` at post-create. The devcontainer is a base image; uv2nix only knows *its own* `uv.lock`, not consumers'. |
| **D** | Hand-rolled `vigUtils`/`pipLicenses`/`pythonEnv` | **Eliminate** — the genuine win; uv2nix builds `pythonEnv` from `uv.lock` (still likely one `pip-licenses` override). |
| **D′** | Native-wheel loader/`LD_LIBRARY_PATH` need *if `pythonEnv` gains a C-ext wheel* | **Eliminate automatically** for PT_INTERP/RPATH via autoPatchelf; **relocate** only the *external-system-lib* case into a bounded, fail-fast `buildInputs` override. Latent today (runtime deps are pure Python). |
| **E** | npm prefix (#728), docker→podman shim (#740) | **Leave** — not Python; wholly out of scope. |

So of the eight issues #775 cites: **#683** would be eliminated for the project
venv (already cheaply fixed); **#698/#703/#735/#736** are *left* (they serve
pre-commit and consumer runtime wheels, not our `uv.lock`); **#697** is already
resolved a different way (flake-sourced `language: system`); **#728/#740** are not
Python at all. The manylinux-wheel elimination uv2nix does offer applies to wheels
in a venv this repo's `pythonEnv` does not currently contain.

## Impact

### Migration cost

- New flake inputs (`pyproject-nix`, `uv2nix`, `build-system-pkgs`) + a
  `pyprojectOverrides` overlay; rework of `pythonEnv` and, under Option B, of the
  dev-shell/image `uv sync` flow (plus a `mkEditablePyprojectOverlay` for the
  editable `vig-utils`).
- Ongoing: a per-problematic-wheel override maintained as `uv.lock` evolves (near
  zero with `sourcePreference = "wheel"` while deps stay pure Python); larger
  lock/Renovate surface.

### Risk to the reproducible-image-digest goal

- A uv2nix venv is itself a reproducible closure, so it does **not** inherently
  threaten the digest — *if* adopted narrowly (C2) and pinned. Option B's larger
  surface (more inputs, autoPatchelf over prebuilt wheels) is more moving parts to
  keep byte-stable across the amd64+arm64 matrix. Because the substrate in **C**
  must remain for consumers regardless, adoption does not let us *remove* the
  digest-relevant loader/`LD_LIBRARY_PATH` config — cost without the
  simplification that would justify the risk.

### Compatibility

- Breaking changes: none for consumers (this is an internal build-mechanism ADR;
  no adoption is recommended). Under a future C2, the dev-loop contract (`just
  sync` / editable `vig-utils`) must be preserved via the editable overlay.

## Decision & Recommendation

**Defer (do not adopt now).** uv2nix/pyproject-nix are a *good* fit for their
actual job — building a hermetic project venv and eliminating manylinux-wheel
loader breakage for the wheels **in that venv**, automatically. The catch is that
this repo's scar tissue does not live there. It is dominated by two surfaces
uv2nix cannot see — **pre-commit's own hook environments** (B) and the **image's
runtime substrate for downstream/consumer wheels** (C) — plus two non-Python items
(E), while the venv uv2nix *would* build (`pythonEnv`) is entirely pure Python
today. uv2nix's only genuine contribution here is tidying two hand-rolled
derivations (D), at the price of three flake inputs, an override overlay, and a
regressed live `uv` dev-loop. It therefore **leaves** far more of the named scar
tissue than it **eliminates**. Keep the status quo, whose shims are small,
documented, and load-bearing.

### Reconsider if

- `pythonEnv`'s **runtime** dependency set grows one or more **native-wheel**
  packages (today all pure Python) — the point at which uv2nix's automatic
  autoPatchelf starts paying for itself.
- We decide to **bake a fully hermetic project venv into the image** (rather than
  the current network-populated-at-post-create model), making `mkVirtualEnv`'s
  reproducible closure directly valuable.
- The maintenance calculus shifts (e.g. `pythonEnv` accretes several fragile
  hand-rolled derivations) such that a lockfile-driven build clearly beats the
  bespoke `buildPythonPackage` set.

If revisited, prefer **Option C2** (image `pythonEnv` only, `sourcePreference =
"wheel"`) as the smallest, lowest-risk entry point.

## References

- Related issue: #775 (spike); root-cause issues #683, #697, #698, #703, #728,
  #735, #736, #740; PR #670 roadmap (thread A).
- In-repo: [`flake.nix`](../../flake.nix), [`docs/NIX.md`](../NIX.md),
  `docs/issues/issue-683.md`, `docs/issues/issue-697.md`,
  `docs/issues/issue-698.md`, `docs/issues/issue-703.md`.
- Prior art / upstream: `pyproject-nix/uv2nix`, `pyproject-nix/pyproject.nix`,
  `pyproject-nix/build-system-pkgs`. Mechanism confirmed from the uv2nix
  getting-started + overriding docs: wheels are autoPatchelf'd automatically
  (`overrides-wheels.nix`); external native libs use a bounded, fail-fast
  `buildInputs` override; `sourcePreference` has no default; pre-commit hook envs
  are explicitly out of scope.
