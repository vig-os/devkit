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

## Updating

- **Downstream dev environment:** `nix flake update vigos` (or re-run
  `install.sh --force` to refresh the scaffold; your `flake.nix`/`.envrc`/
  `pyproject.toml` and a populated `.devcontainer/` are preserved).
- **Toolchain versions / CVEs:** advance the pinned `nixpkgs` revision
  (Renovate's `nix` manager opens the PR); `flake.lock` is the controlling
  version document.
