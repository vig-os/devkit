# Nix in the vigOS devcontainer

This repository is **Nix-first**: the Nix flake (`flake.nix`) is the single source
of truth for the development toolchain *and* the basis of the built devcontainer
image, so the dev-shell and the image can never drift. This document is the
consolidated reference for how the flake is structured and why. For day-one
onboarding (clone → `direnv allow`) see the fast path in
[`CONTRIBUTE.md`](../CONTRIBUTE.md); for the downstream production-image pattern
see [`docs/NIX2CONTAINER.md`](NIX2CONTAINER.md).

## The flake as the toolchain SSoT

The flake exposes one list, `devTools`, that enumerates every CLI in the
environment (`just`, `git`, `gh`, `uv`, `nodejs`, `jq`, `tmux`, `ripgrep`, `fd`,
`bat`, `eza`, `delta`, `lazygit`, `zoxide`, `starship`, `neovim`, `claude-code`,
`podman`, `hadolint`, `taplo`, `shellcheck`, …). Adding a tool there adds it
everywhere — the dev-shell now and the image's `imageTools` set.

- **`devShells.default`** is built from `devTools` via `mkProjectShell`, so
  `nix develop` (or `direnv`) gives you exactly that toolchain.
- **`mkProjectShell`** is also a reusable `lib` output: downstream repos build
  their own shell as `devTools ++ extraPackages` (see the scaffolded
  `assets/workspace/flake.nix`).
- **`overlays.default`** and **`lib.{mkProjectShell,devTools}`** are exported as
  system-independent outputs so consumers can follow the same pinned `nixpkgs`.

### Dev-shell ↔ image parity guard

Because both the dev-shell and the image are assembled from `devTools`, a single
test keeps them honest. `tests/test_flake_devshell.py` reads the binary names
straight from the flake (`nix eval .#devShellTools`, derived from each package's
`meta.mainProgram`) and runs `nix develop -c <bin> --version` for every tool,
asserting it exits 0. The test list is generated *from* the SSoT, so it can never
drift from the tool list it guards. It is skipped automatically when `nix` is not
on `PATH` (e.g. the podman image CI lane).

## Stable / unstable channel split and the fast-mover overlay

The flake pins two inputs:

- **`nixpkgs`** → `github:NixOS/nixpkgs/nixos-26.05` — the controlled, pinned
  stable channel (the "version document", anchored by `flake.lock`). Everything
  comes from here unless explicitly overridden.
- **`nixpkgs-unstable`** → `github:NixOS/nixpkgs/nixpkgs-unstable` — overlaid
  **only** for a small set of fast-moving tools.

The `overlay` (also exported as `overlays.default`) replaces just the `fastMovers`
list — `uv`, `gh`, and `claude-code` — with their `nixpkgs-unstable` builds.
These ship frequently and we want the latest version in both shell and image;
everything else stays on the pinned stable channel for reproducibility.

### uv and the project interpreter

The dev-shell carries no Python on `PATH` (the project venv is uv-managed), so
`uv sync` must be told which interpreter to build the venv from. `mkProjectShell`
pins a Nix store CPython via `UV_PYTHON` and forbids downloads with
`UV_PYTHON_DOWNLOADS=never`. This avoids letting the nixpkgs `uv` fetch a managed
CPython: that download is a generic, dynamically-linked ELF a NixOS host cannot
execute out of the box (no FHS `ld-linux`), so `uv sync` (`just init`) aborted
there (#683). A store interpreter is patched to the store loader and runs in the
dev-shell on both NixOS and FHS hosts. The **image** path uses the same two
variables, baking the interpreter and toolchain from nixpkgs.

**CI is the exception.** The `provision-via-flake` jobs (#632) run *outside*
`nix develop` — they only prepend the dev-shell's tool `PATH` — on an FHS runner,
where a Nix store interpreter cannot load pre-commit's manylinux-wheel C
extensions (`libstdc++.so.6`). So the dev-shell also keeps
`UV_PYTHON_DOWNLOADS_JSON_URL` set (pinned to the provisioned `uv` release), and
the `setup-env` action forwards **that URL only** — not `UV_PYTHON` — so the
runner's stripped nixpkgs `uv` downloads a managed CPython instead. Locally the
pin wins and no download happens; the URL matters only on the CI runner.

## The Nix-built image

`packages.devcontainerImage` is assembled entirely by Nix via
**`dockerTools.buildLayeredImage`** — not a Dockerfile `FROM`. Key properties:

- **Bit-reproducible.** Every build from the same commit and `flake.lock`
  produces a byte-identical image closure (the epic's "identical image digest on
  rebuild" criterion). A deterministic `created = "1970-01-01T00:00:00Z"` epoch
  keeps the digest stable; there is no non-deterministic upgrade step.
- **Multi-arch.** The image builds natively on an amd64 + arm64 matrix (no QEMU,
  no cross-compilation); per-arch discovery tags are assembled into a multi-arch
  index.
- **Contents = `imageTools`.** That is `devTools` plus the runtime substrate a
  bare layered image lacks (an FHS base distro would otherwise supply it): the
  Nix evaluator (`nix`, `direnv`, `nix-direnv`), `glibcLocales` for locale
  support, the project Python env (`vig-utils` + `pip-licenses` baked via
  `python314.withPackages`), `pre-commit`/`ruff`/`bandit`, Rust/just tooling
  (`cargo-binstall`, `just-lsp`, `typstyle`), core GNU utilities, `cacert`,
  `openssh`, and `dockerTools.fakeNss` (a root uid-0 user database, without which
  `ssh`/`tmux`/`git` fail with "No user exists for uid 0").

A `bootstrap` layer bakes the workspace assets, the pre-commit cache dir, the
template `.venv` scaffold, a sticky `/tmp`, and the `precommit`/`cc`/`cld`
aliases. The image's interpreter is pinned via `UV_PYTHON=<nix python3.14>` and
`UV_PYTHON_DOWNLOADS=never`.

### Host container runtime (`policy.json`)

`just build` ends in `podman load -i result`, and podman's containers/image
library refuses to load any image unless a signature-verification `policy.json`
exists at `~/.config/containers/policy.json` or `/etc/containers/policy.json`
(this podman build has no `--signature-policy` flag and no env override). The
flake dev-shell ships the **podman CLI** but not that host file: on NixOS the
`virtualisation.containers` module normally installs `/etc/containers/policy.json`,
so a host that gets podman purely from the dev-shell never receives one and
`podman load` fails — even though `podman info` (the `just init` advisory check)
is green.

`just init` closes this gap: if neither lookup path has a policy, it writes the
user-level default `~/.config/containers/policy.json` with the standard permissive
content (the same `{ "default": [ { "type": "insecureAcceptAnything" } ] }` that
`containers-common` / the NixOS module ship). The write is idempotent and never
overwrites a system or user policy. To do it by hand:

```bash
mkdir -p ~/.config/containers
printf '{ "default": [ { "type": "insecureAcceptAnything" } ] }\n' > ~/.config/containers/policy.json
```

## Evaluator and pre-commit decisions

These are decided inline in `flake.nix`; summarized here.

- **CppNix vs Lix (#634).** The image ships upstream **CppNix** (`pkgs.nix`) as
  the in-container evaluator. It is the channel default, needs no overlay, and the
  flake is installer-agnostic, so swapping to `pkgs.lix` later is a one-line
  change. `pkgs.lix` is left out for now to keep the closure smaller.
- **`pre-commit` vs `prek` (#40).** The image bakes upstream **`pre-commit`** to
  match the prior Debian build and the pinned `pyproject` version. Migrating the
  cache layer to `prek` is deferred to #40; both are in nixpkgs, so it is a
  drop-in swap once that issue lands.

## Cachix and the `direnv allow` onboarding flow

The dev-shell closure is published to the public **`vig-os`** Cachix binary
cache, so the first `direnv allow` is a binary fetch (seconds) rather than a
from-source build. To use it, enable flakes and add the substituter to your Nix
config (`~/.config/nix/nix.conf` or `/etc/nix/nix.conf`):

```conf
experimental-features = nix-command flakes
substituters = https://cache.nixos.org https://vig-os.cachix.org
trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=
```

Pulling from the public `vig-os` cache needs no token (`cachix use vig-os` writes
the same lines). Then:

```bash
git clone git@github.com:vig-os/devcontainer.git
cd devcontainer
direnv allow        # first allow fetches the closure from Cachix
```

The committed `.envrc` uses [nix-direnv](https://github.com/nix-community/nix-direnv):
the dev-shell evaluation is cached and GC-rooted under `.direnv/` (gitignored), so
re-entry is instant and the closure is never garbage-collected. nix-direnv
self-bootstraps the pinned library on first allow, or uses your
`~/.config/direnv/direnvrc` installation if you already source it; it falls back
to bare `use flake` when unavailable. The full fast path lives in
[`CONTRIBUTE.md`](../CONTRIBUTE.md).

## How `nixpkgs` bumps flow (Renovate + vulnix)

The pinned `nixpkgs` revision in `flake.lock` defines the image's entire CVE
surface, so advancing the pin is the **primary CVE-remediation lever** (see
[`docs/CONTAINER_SECURITY.md`](CONTAINER_SECURITY.md) for the full strategy).
Renovate keeps the pin current through `renovate.json`:

- The **`nix` manager** detects flake inputs and proposes pinned-input updates
  (committed as `build(nix): …`).
- **`lockFileMaintenance`** (enabled, scheduled weekly) refreshes the locked
  revisions of all inputs so upstream security fixes land through the normal
  PR/CI gate rather than a manual `nix flake update`.

**vulnix before/after requirement.** A `nixpkgs`-rev bump does not declare *which*
CVE it fixes — the `nix` manager reports only the old → new revision. To preserve
the audit trail, each `flake.lock` / `nixpkgs`-bump PR should include a `vulnix`
scan diff taken **before and after** the bump, showing which advisories the new
revision clears (or introduces). The nightly `vulnix` scan runs against the
`devcontainerImageEnv` closure; HIGH/CRITICAL findings are gated by `vulnix-gate`
against the `.vulnixignore` exception register.

## Publish cutover

The Nix image build is currently in the **discovery phase**: the workflows are
non-publishing (`continue-on-error`) and touch only disposable discovery tags. The
publish-cutover — flipping the versioned/`:latest` publish to the Nix builder and
making the `vulnix` gate blocking — is tracked in **issue #639** (the release
pipeline exposes a `builder: debian|nix` selector for the deliberate cutover run).

## See also

- [`CONTRIBUTE.md`](../CONTRIBUTE.md) — onboarding fast path (clone → `direnv allow`).
- [`docs/NIX2CONTAINER.md`](NIX2CONTAINER.md) — the downstream production-image
  pattern with `nix2container` (distinct from this image's `buildLayeredImage`).
- [`docs/CONTAINER_SECURITY.md`](CONTAINER_SECURITY.md) — the full CVE-patching
  strategy (pinned `nixpkgs`, `vulnix`, SBOM/Trivy, exception registers).
- [`flake.nix`](../flake.nix) — the authoritative source for all of the above.
