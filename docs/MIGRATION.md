# Migrating to the Nix devcontainer

This document describes the development-environment paradigm introduced by the
Nix migration and what it means for projects that consume the vigOS
devcontainer. It ships inside the image at `/root/assets/MIGRATION.md`; the
canonical copy lives at `docs/MIGRATION.md`.

For the flake architecture and contributor onboarding see
[`docs/NIX.md`](./NIX.md); for the security posture see
[`docs/CONTAINER_SECURITY.md`](./CONTAINER_SECURITY.md).

## What changed

The devcontainer used to be a Debian image (`FROM python:3.14-slim-…`) built
with a `Containerfile` and provisioned with `apt` + ad-hoc installers. It is now
a **Nix flake** that is the single source of truth for one toolchain, consumed
two ways:

- **Container image** — assembled by `dockerTools.buildLayeredImage` (no base
  distro, no `Dockerfile FROM`), bit-reproducible, and built natively for
  `amd64` and `arm64`. Published as `ghcr.io/vig-os/devcontainer`.
- **Bare-nix dev-shell** — the same toolchain via `nix develop` / `direnv`,
  consumed as a flake input (`vigos.url = "github:vig-os/devcontainer"`).

The toolchain is defined once, in `flake.nix`'s `devTools` list. A parity test
guarantees the dev-shell and the image never drift. There is no second
dependency manifest (`requirements.yaml` is gone); to change the toolchain you
edit `devTools`, and to update it downstream you bump the flake input
(`nix flake update vigos`).

## The two delivery modes

`install.sh … --mode <devcontainer|direnv|both>` scaffolds a consumer for either
or both modes:

- **`devcontainer`** — a `.devcontainer/` that pulls the published image. The
  workspace is mounted; first-run `post-create.sh` sets up git/gh/pre-commit and
  runs `just sync`.
- **`direnv`** — a minimal `flake.nix` + `.envrc` stub. `direnv allow` (or
  `nix develop`) drops you into the shared toolchain on the host, no container.
  The stub is never overwritten on re-scaffold; update with `nix flake update`.

## What a consumer needs to know

The image is a **pure-Nix userland**, not Debian. The migration restored the
FHS conveniences real tooling assumes, but the contract differs from the old
image:

- **No `apt`.** The image has no `apt`/`dpkg`. Do not `apt-get install` in
  `post-create.sh`; rely on the baked toolchain, `uv`/`npm` for language deps, or
  Nix (below). Post-create steps that shell out to `apt` should be removed.
- **`/usr/bin/env` exists.** The universal `#!/usr/bin/env <interp>` shebang
  works (so `node_modules/.bin/*`, etc. run).
- **`npm install -g` works.** The global prefix is `/usr/local` (on `PATH`);
  globally-installed CLIs resolve. Prefer `npx` / local devDependencies where you
  can.
- **`docker` resolves to `podman`.** The image ships `podman` plus a
  `docker → podman` shim. Docker-out-of-Docker works when the host container
  socket is mounted and `CONTAINER_HOST`/`DOCKER_HOST` are set (the scaffolded
  `docker-compose.yml` does this). There is no Docker engine.
- **Python is CPython 3.14, uv-managed.** The project venv lives at
  `/root/assets/workspace/.venv` and is populated by `just sync` (`uv sync`).
  Pin `requires-python` as a **range** (`>=3.14,<3.15`), never an exact patch —
  `flake.lock` is the reproducibility anchor, and an exact `==3.14.x` pin can be
  unsatisfiable against the image's interpreter.
- **Pre-compiled PyPI (manylinux) wheels run.** numpy/scipy/pandas and
  PyPI-distributed tools (`pymarkdown`'s `pyjson5`, etc.) load: the image ships
  the FHS dynamic loader and the C++/zlib runtime on the loader path.
- **pre-commit linters come from the flake.** `ruff`/`ruff-format`/`typos` are
  `language: system` hooks sourced from the baked toolchain (not upstream
  manylinux wheels), so they run without per-host setup.

## Adding tools the image does not ship

The image stays deliberately minimal — it ships build automation, git/gh,
`uv`/Python, Node, shell tooling, linters, and the agent toolkit, but **not**
language toolchains like Rust, Go, or a C/C++ compiler. Source extra tools
**on-demand** rather than growing the base image:

- **Per-project flake (preferred, reproducible).** In a `direnv`-mode project,
  add them to `mkProjectShell`'s `extraPackages` (a plain list):

  ```nix
  vigos.lib.mkProjectShell {
    inherit pkgs;
    extraPackages = [ pkgs.cargo pkgs.rustc pkgs.pkg-config pkgs.openssl ];
  };
  ```

  or bring your own pinned toolchain (e.g. a `rust-overlay`) in the project
  `flake.nix`. This is pinned, reproducible, and shared by `direnv`, `nix
  develop`, and CI.
- **Ad-hoc inside the image.** The baked Nix has `nix-command`/`flakes` enabled,
  so `nix shell nixpkgs#<pkg> -c …` and `nix develop` work out of the box,
  including local builds. Good for one-offs; not a substitute for a pinned
  project toolchain (the default registry tracks `nixpkgs-unstable`).

If a toolchain recurs across vigOS projects, promote it to a shared, opt-in
module rather than baking it into every consumer's image.

### The native-build contract

`uv sync` compiles a dependency from sdist whenever PyPI has no wheel for the
image's CPython (`cp314`) — common for scientific packages (pycatima, f2py
extensions, anything built with scikit-build-core or meson-python). The image
ships **no C/C++ compiler**, so where that toolchain comes from is an explicit,
tiered contract:

1. **Pure-Python / wheel-only projects — nothing to do.** Pre-compiled
   manylinux wheels load out of the box (see above); the image works as-is.

2. **Native deps, `direnv` mode (preferred).** Provide the toolchain via the
   project flake:

   ```nix
   devShells.default = vigos.lib.mkProjectShell {
     inherit pkgs;
     extraPackages = [
       pkgs.stdenv.cc # C/C++ compiler wrapper: puts cc/c++ on PATH, exports CC/CXX
       pkgs.cmake
       pkgs.pkg-config
     ];
   };
   ```

   Inside `nix develop` / `direnv` the stdenv compiler wrapper exports working
   `CC`/`CXX`, so build backends find a real compiler regardless of what the
   image's baked interpreter recorded at image-build time (the sysconfig
   mechanics are tracked in
   [#879](https://github.com/vig-os/devcontainer/issues/879)). This path is
   field-validated by the 0.4.0 downstream runs
   ([#639](https://github.com/vig-os/devcontainer/issues/639)).

3. **Native deps, `devcontainer` mode (middle path).** No direnv migration
   required: the baked Nix has flakes enabled, so run the sync *through* a Nix
   shell inside the container:

   ```bash
   # Against the project flake (pinned, reproducible):
   nix develop -c just sync

   # Ad-hoc, when the project has no flake yet:
   nix shell nixpkgs#gcc nixpkgs#cmake -c uv sync
   ```

   This is the supported interim answer for devcontainer-mode repos whose
   dependencies lack `cp314` wheels. The pinned `nix develop -c` form also
   works in CI until the nix-direct CI lane
   ([#854](https://github.com/vig-os/devcontainer/issues/854)) lands; #854
   tracks running consumer CI inside the project devshell so the contract is
   enforced in CI, not just locally.

#### Worked example: heavyweight scientific dependencies

A bare compiler is often not enough. An extension that links against Geant4 or
ROOT needs the library's headers, shared objects, and CMake package config at
build time — none of which a fatter base image could supply generically. The
project flake provides all of it, pinned:

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  extraPackages = [
    pkgs.stdenv.cc
    pkgs.cmake
    pkgs.pkg-config
    pkgs.geant4 # headers + libs + Geant4 CMake config
    pkgs.root # ROOT, likewise
  ];
};
```

`nix develop` composes the include/library/CMake search paths from these
packages, so the build backend compiles against the exact Geant4/ROOT revision
pinned by the project's `flake.lock`. This is why the answer to "the build
needs gcc" is the flake, not the image: the same mechanism scales from a bare
compiler to a full scientific stack.

#### Non-goal: a C/C++ toolchain in the base image

The published image will **not** ship gcc/cmake:

- it breaks the minimal-image stance and inflates every consumer, most of
  which never compile anything;
- it still would not suffice — real native builds also need third-party
  headers, libraries, and build config (see the Geant4 example above), which
  only a pinned project flake provides reproducibly.

The in-image behavior when no toolchain is provided is tracked in
[#879](https://github.com/vig-os/devcontainer/issues/879); the toolchain
itself always comes from one of the tiers above.

## Updating

- **Downstream dev environment:** `nix flake update vigos` (or re-run
  `install.sh --force` to refresh the scaffold; your `flake.nix`/`.envrc`/
  `pyproject.toml` and a populated `.devcontainer/` are preserved).
- **Toolchain versions / CVEs:** advance the pinned `nixpkgs` revision
  (Renovate's `nix` manager opens the PR); `flake.lock` is the controlling
  version document.

## Upgrading an existing 0.3.x consumer — manual steps

`install.sh --version <X> --force` refreshes the scaffold and pins `<X>` in
`.vig-os`, but files you own are **preserved, not migrated**. Field-validated
checklist ([#859](https://github.com/vig-os/devcontainer/issues/859)) after the
re-scaffold:

1. **Base recipes moved into `justfile.project`** — 0.4.0 retired
   `.devcontainer/justfile.base`; `lint`/`format`/`precommit`/`test`/
   `test-cov`/`sync`/`update` now live in `justfile.project`, which is
   preserved on upgrade. The shipped `ci.yml` calls `just sync` /
   `just precommit` / `just test`, so the installer appends any of these
   recipes your preserved file does not already resolve (a clearly marked
   block, [#877](https://github.com/vig-os/devcontainer/issues/877)) and
   removes the stale `.devcontainer/justfile.base`. Review the appended
   block and fold it into your own recipes; also verify the root `justfile`
   still carries the scaffold `import?` lines — without them no layered
   recipe is reachable (the installer warns if the block is missing).
2. **`.pre-commit-config.yaml` is preserved on upgrade** — earlier upgrades
   replaced it wholesale, silently dropping repo-specific global and per-hook
   `exclude:` patterns (the autofix hooks then rewrote data files they must
   never touch, [#878](https://github.com/vig-os/devcontainer/issues/878)).
   The installer now keeps your file and prints a diff against the incoming
   template — review it and fold in the template evolution you want (e.g.
   `default_language_version`, runner-compat fixes, new hooks). It also warns
   if the preserved config does not parse under the shipped runner; check
   with `prek validate-config .pre-commit-config.yaml`.
3. **`pre-commit` invocations → `prek`** — the `pre-commit` binary is gone
   from the 0.4.0 image and venv; the hook runner is `prek` (a drop-in for
   `run`-style invocations, [#778](https://github.com/vig-os/devcontainer/issues/778)).
   Rename every invocation in files the upgrade preserves or your repo owns:
   the `justfile.project` `precommit` recipe (`uv run pre-commit run
   --all-files` → `prek run --all-files`), repo-managed `.githooks/` scripts
   beyond the scaffold-shipped three (e.g. a `pre-push` hook), hook `entry:`
   lines in `.pre-commit-config.yaml`, and CI configs. The installer scans
   the preserved surfaces and warns with `file:line`
   ([#881](https://github.com/vig-os/devcontainer/issues/881)). As a bridge,
   0.4.x images ship a deprecated `pre-commit → prek` shim that prints a
   stderr notice and is **removed in 0.5** — treat the notice as the
   migration deadline, not a supported path. While editing old `.githooks`
   scripts, also change `#!/bin/bash` shebangs to `#!/usr/bin/env bash`:
   `/bin/bash` does not exist on NixOS hosts, so those hooks fail outside
   the container even after the rename.
4. **Recipe renames** — the managed base recipes are now `devc-*`-namespaced
   and the template test recipe is `just test` (formerly `just test-pytest`).
   Run `just --list` once and update any scripts/muscle memory.
5. **typos config precedence** — if your repo owns a `typos.toml` or
   `_typos.toml`, it silently **shadows** the shipped `.typos.toml`. Merge the
   shipped `[default.extend-words]` entries (`Nd`, `unexcepted`, `ba` — needed
   by scaffold-shipped content such as `version-check.sh` and the synced
   `.devcontainer/CHANGELOG.md`) into your file.
6. **Committed binary/generated artifacts** (plot exports, PDFs, golden `.bin`
   fixtures, SVGs): add them to your typos `[files] extend-exclude` and
   consider a global `exclude:` in `.pre-commit-config.yaml` so the autofix
   hooks (end-of-file-fixer, trailing-whitespace) don't rewrite them.
7. **Project name re-derivation** — the re-scaffold substitutes placeholders
   from the current directory/`--name`; template-origin files (e.g.
   `tests/test_example.py`) may be rewritten to a name that differs from your
   original scaffold. Review the diff before committing.

## The retired Debian line (historical)

The Debian build path was decommissioned in
[#642](https://github.com/vig-os/devcontainer/issues/642): the final
Debian-built release is **0.3.9**, and every release from 0.4.0 onward is
Nix-built. Released images are never deleted, so 0.3.9 remains pullable
(`DEVCONTAINER_VERSION=0.3.9` in the repo-root `.vig-os`), but the line is
frozen — it receives no CVE fixes and is not a supported rollback track.

## Upcoming rename: `devcontainer` → `devkit`

The repository and image are scheduled to be renamed to **`devkit`** in the
release cycle after the Nix cutover
([#781](https://github.com/vig-os/devcontainer/issues/781)). GitHub redirects
the repository URL, but the image moves to a **new** GHCR package
(`ghcr.io/vig-os/devkit`) — a one-time `install.sh --force` re-scaffold will
migrate consumers. Existing `ghcr.io/vig-os/devcontainer` images remain
pullable indefinitely.
