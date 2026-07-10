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
`podman`, `taplo`, `shellcheck`, …). Adding a tool there adds it
everywhere — the dev-shell now and the image's `imageTools` set.

- **`devShells.default`** is built from `devTools` via `mkProjectShell`, so
  `nix develop` (or `direnv`) gives you exactly that toolchain.
- **`mkProjectShell`** is also a reusable `lib` output: downstream repos build
  their own shell as `devTools ++ extraPackages` (see the scaffolded
  `assets/workspace/flake.nix`), optionally composing opt-in
  [capability modules](#capability-modules-mkprojectshell-modules) via
  `modules = [ "native" ]`. For projects that compile native Python
  extensions, the `native` module (or a hand-rolled `extraPackages`) is where
  the C/C++ toolchain comes from — see the
  [native-build contract](./MIGRATION.md#the-native-build-contract).
- **`mkProjectServices`** is the local-dev-services counterpart (#795): a `lib`
  builder that turns declared [services-flake](https://github.com/juspay/services-flake)
  modules into a daemonless `process-compose` stack (`nix run .#services`) —
  see [Local dev services](#local-dev-services-mkprojectservices) below.
- **`overlays.default`** and **`lib.{mkProjectShell,mkProjectServices,devTools}`**
  are exported as system-independent outputs so consumers can follow the same
  pinned `nixpkgs`.
- **`nixosModules.default`** / **`homeManagerModules.default`** install the same
  `devTools` set into a NixOS or home-manager configuration — flip
  `programs.vigos-devtools.enable = true`. `claude-code` is unfree, so the
  consumer must allow it (`nixpkgs.config.allowUnfree`). The NixOS module applies
  `overlays.default` for the fast-movers; a home-manager consumer that passes its
  own `pkgs` should apply the overlay itself (home-manager rejects a module-set
  `nixpkgs.overlays` in that case).
- **`apps.install`** wraps the host installer, so `nix run github:vig-os/devcontainer#install -- --help`
  bootstraps a consumer project straight from the flake — no prior `curl | bash`.
  `install.sh` remains the behavior SSoT; the app just wraps it.

### Formatting, linting, and flake quality gates

`nix fmt` runs [`treefmt`](https://github.com/numtide/treefmt-nix) over every
supported language in one pass — `nixfmt-rfc-style` for `*.nix`, `ruff format` for
`*.py`, `taplo` for `*.toml`. It wraps the same formatters the pre-commit hooks
run, so the editor `nix fmt`, the hooks, and CI all agree on one formatting.

`nix flake check` runs the lightweight gates the sandbox can (recursive `nix`
access is unavailable, so the dev-shell/image parity test stays a CI pytest):

- **`formatting`** — the tree is `treefmt`-clean (the `nix fmt` idempotency gate).
- **`deadnix`** / **`statix`** — `flake.nix` carries no dead Nix code or lint
  anti-patterns. Scoped to the authored flake; the downstream scaffold
  (`assets/workspace/flake.nix`) and example keep their idiomatic `{ self, … }`
  signatures whose intentionally-unused args those linters would otherwise flag.
- **`devShell`** — the dev-shell closure builds.
- **`devShellTools`** — the parity-test SSoT evaluates to a non-empty list.
- **`module-<name>`** — one devshell build per shipped capability module,
  generated from the `nix/modules/` registry (a module cannot ship without
  its check).

### Dev-shell ↔ image parity guard

Because both the dev-shell and the image are assembled from `devTools`, a single
test keeps them honest. `tests/test_flake_devshell.py` reads the binary names
straight from the flake (`nix eval .#devShellTools`, derived from each package's
`meta.mainProgram`) and runs `nix develop -c <bin> --version` for every tool,
asserting it exits 0. The test list is generated *from* the SSoT, so it can never
drift from the tool list it guards. It is skipped automatically when `nix` is not
on `PATH` (e.g. the podman image CI lane).

## Capability modules (`mkProjectShell` `modules`)

`mkProjectShell` composes opt-in **capability modules**
([#884](https://github.com/vig-os/devkit/issues/884); contract and
composition rules in
[ADR-capability-modules](rfcs/ADR-capability-modules.md)): a consumer
declares a capability by name instead of hand-picking packages:

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  modules = [ "native" ]; # opt-in capability modules
  extraPackages = [ pkgs.my-extra ]; # per-repo escape hatch, unchanged
};
```

- A module (defined in `nix/modules/`) contributes **packages, env vars, and
  shellHook fragments only** (v1 contract). `extraPackages` wins PATH lookup
  over module packages; the consumer `shellHook` runs last.
- **Zero cost when unused:** `modules = [ ]` (the default) produces a shell
  byte-identical to the pre-module builder — pure-Python consumers are
  untouched, and the **published image stays base-only** (modules are a
  direnv-mode/devshell feature).
- **Shipped:** `native` — `stdenv.cc`, `cmake`, `gnumake`, `pkg-config` plus
  generic `CC=cc`/`CXX=c++` exports; the curated form of the
  [native-build contract](./MIGRATION.md#the-native-build-contract)'s
  preferred tier. **Candidates (ask-gated, not shipped):** `geant4`, `rust`,
  `fortran`/`f2py`, `root`.
- Each shipped module gets a `checks.<system>.module-<name>` devshell build
  and, for `native`, the uv C-extension sdist smoke test in
  `tests/test_flake_modules.py`.

## Home-manager modules — versioning & release policy

The `vigos.*` home-manager modules ([ADR](rfcs/ADR-home-environment-modules.md),
epic #814) are a **second product** of this flake with a consumer-facing API
(their options). Policy:

- **One release train.** Modules ship with the repo's existing tagged releases —
  there is no separate module release cycle. Consumers pin a tag:
  `vigos.url = "github:vig-os/devcontainer?ref=<tag>";` and bump deliberately
  (`nix flake update vigos`). Tracking `main`/`dev` is not a documented
  consumption mode.
- **Scaffold exception.** The workspace scaffold (`assets/workspace/flake.nix`)
  deliberately floats on the default branch so freshly scaffolded projects work
  before their first pin; the comment there points consumers at this policy for
  pinning once they depend on module stability.
- **Dogfood-canary exception.** The maintainer's personal configuration tracks
  `dev` during a module wave's dogfood phase (pre-release canary); the pin-tags
  policy applies to everyone else, and to it once the first module-bearing tag
  ships.
- **Deprecation.** Option renames keep a `lib.mkRenamedOptionModule` shim for
  one release and get a changelog entry. Removals are announced one release
  ahead.
- **Changelog.** Module-facing changes are grouped under a `#### Modules`
  sub-heading inside the relevant Keep-a-Changelog category of `## Unreleased`,
  so consumers can scan API changes without reading image/CI noise.

## Local dev services (`mkProjectServices`)

[ADR-nix-devenv-strategy](rfcs/ADR-nix-devenv-strategy.md) (#794) rejects
`cachix/devenv` as the shared shell builder but adopts the one capability it
bundled that plain `mkShell` lacks: `devenv up`-style orchestration of local
dev services. `mkProjectServices` (#795) is that replacement —
[`process-compose`](https://github.com/F1bonacc1/process-compose) (a single Go
binary: no daemon, no root) driving service definitions from
[`services-flake`](https://github.com/juspay/services-flake) (postgres,
seaweedfs, redis, mysql, grafana, kafka, …).

A consuming repo needs **no extra flake inputs** — both service flakes resolve
from this flake's lock — and wires it exactly like `mkProjectShell`:

```nix
packages.services = vigos.lib.mkProjectServices {
  inherit pkgs;
  modules = [ { services.postgres."db".enable = true; } ];
};
```

Then `nix run .#services` boots the stack (add `--tui=false` for headless use;
Ctrl-C tears everything down). The scaffolded `justfile.project` carries a
commented opt-in `services` recipe wrapping exactly that. Properties worth
knowing:

- **No container daemon.** Services run as native processes; the light
  direnv-mode promise ("no Docker on the host") is preserved.
- **Versions from the pinned `nixpkgs`.** Service binaries come from the
  caller's `pkgs` — the same lock, Renovate flow, and vulnix scanning as the
  toolchain; there are no out-of-lock image tags.
- **State lands in `./data/<name>`** relative to the invocation cwd — add
  `data/` to the repo's `.gitignore` (the scaffold ships this).
- **GC-rooted with the flake** (via direnv's GC root, like the dev-shell) and
  **zero import-from-derivation** — none of devenv's ~165 s cold-eval tax.
- **macOS:** evaluation is cross-platform (guarded by
  `tests/test_flake_services.py` against the darwin eval), but booting is only
  CI-exercised on Linux.

This repo's own flake carries the validating PoC: `nix run .#services` boots
**SeaweedFS (S3 gateway on `:8333`) + Postgres (`:5433`)**, asserted end-to-end
by `tests/test_flake_services.py` with no podman/docker anywhere in the test.

### Decision: standalone `evalModules`, not flake-parts

`services-flake` is idiomatically consumed via `flake-parts`, while this flake
(and the consumer stub) are `flake-utils`/`eachDefaultSystem`. The ADR left the
adopt-vs-manual question to #795; the resolution: **neither** — services-flake
documents a first-class no-flake-parts path
([`example/without-flake-parts`](https://github.com/juspay/services-flake/tree/main/example/without-flake-parts)),
where `process-compose-flake`'s `lib.evalModules` evaluates the same modules
standalone. `mkProjectServices` wraps that, so the flake structure is untouched
and consumers see a plain derivation. Both new inputs are dependency-free leaf
flakes: `flake.lock` gained exactly two entries and nothing to `follows`.

Measured cost (x86_64-linux, warm store): flake eval of the services app
~0.8 s, PoC closure build/substitute ~3 s, `process-compose` boot-to-healthy
(both services) ~3 s. For comparison, the devenv path this replaces paid ~165 s
of IFD on a cold eval (exo-pet/exo-fleet#76).

### PoC S3 service: SeaweedFS, not MinIO

Issue #795 originally named MinIO, but `nixpkgs` marks `minio` **abandoned
upstream** with six unfixed CVEs (`meta.knownVulnerabilities`, both channels) —
building it requires a `permittedInsecurePackages` exception, the wrong default
for the org's blessed PoC. The PoC therefore ships the maintained,
S3-compatible **SeaweedFS** (`services.seaweedfs` with `filer.enable` +
`s3.enable`). A repo that truly needs MinIO for prod parity can still declare
`services.minio` and scope the insecure-package exception into the `pkgs` it
passes — consciously, per repo, never in the shared helper.

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

**CI is the exception.** The `setup-env` CI jobs (#632, #720) run *outside*
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
  `python314.withPackages`), the `prek` hook runner (via `devTools`) + `bandit`,
  Rust/just tooling
  (`cargo-binstall`, `just-lsp`, `typstyle`), core GNU utilities, `cacert`,
  `openssh`, and `dockerTools.fakeNss` (a root uid-0 user database, without which
  `ssh`/`tmux`/`git` fail with "No user exists for uid 0").

A `bootstrap` layer bakes the workspace assets, the prek cache dir, the
template `.venv` scaffold, a sticky `/tmp`, and the `precommit`/`cc`/`cld`
aliases. The image's interpreter is pinned via `UV_PYTHON=<nix python3.14>` and
`UV_PYTHON_DOWNLOADS=never`.

### Building and iterating the image locally

Most contributors never build the image. `nix develop`/direnv gives the dev-shell
fast path for day-to-day work, and CI publishes the image to GHCR — so `just test`
pulls the published `dev` tag rather than building. Build locally only when you
are changing the **image itself** (its `imageTools`/`bootstrap` contents, baked
workspace assets, or the `flake.nix` image wiring) and want to test before pushing:

```bash
just build          # nix build .#devcontainerImage → podman load → tag <repo>:dev
just test-image     # run tests/test_image.py against the freshly loaded dev tag
```

`just build` tags the loaded image `<repo>:dev`; `just test-image`, `just
test-integration`, and `just test` all default to that `dev` tag (and
auto-`just build` it if it is missing). The iterate loop for image changes is
therefore: edit `flake.nix` → `just build` → `just test-image` → repeat. `nix
build` is content-addressed, so an unchanged closure rebuilds instantly and the
`no_cache` argument is a no-op.

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
- **`pre-commit` → `prek` (#778, closes #40).** The git-hook runner is now the
  Rust **`prek`** (a drop-in for the Python `pre-commit`, faster and one fewer
  manylinux/FHS consumer). `prek` lives in the `devTools` SSoT, so it ships in
  both the dev-shell and the image; the standalone Python `pre-commit` is dropped
  from both. The `.githooks` shims (wired via `core.hooksPath`) call `prek run`,
  `just precommit` runs `prek run --all-files`, and the baked hook cache is
  `PREK_HOME=/opt/prek-cache`.

  **One hook definition, three renders (#883; supersedes the former
  "two hook artifacts" model).** `nix/hooks.nix` defines every pre-commit hook
  exactly once, and the flake renders it three ways:

  1. The flake's **`checks.pre-commit`** (built by `git-hooks.nix` with
     `package = pkgs.prek`) evaluates the definition's **sandbox-pure
     profile** under `nix flake check` — no network, no project venv. It
     reuses `treefmtEval` for the single formatting hook (nixfmt +
     ruff-format + taplo), the nix-provided pure linters (ruff, shellcheck,
     yamllint, typos, `taplo lint`), the `just --fmt --check`
     justfile-format check (the runner hook mirrored in check mode since the
     sandbox is read-only), the `pre-commit-hooks` meta hooks, and the
     `vig-utils`/`bandit` hooks wired to hermetic Nix binaries
     (`${vigUtils}/bin/…`, `${pkgs.bandit}/bin/bandit`).
  2. The committed **`.pre-commit-config.yaml`** (and its scaffold copy in
     `assets/workspace/`) is the definition's **PATH-portable render** — the
     runner config `prek` executes locally, in the image, and in the
     downstream scaffold. It stays a committed file rather than a gitignored
     store artifact so it is portable and does not churn on nixpkgs bumps,
     but it is no longer hand-maintained in parallel:
     `tests/test_flake_hooks.py` diffs the render
     (`nix eval .#lib.hooksPortable`) against both committed files
     (normalized, every hook id/args/files/excludes/stages) and fails CI on
     any drift. The former `sync-manifest` transform chain for the scaffold
     copy is retired — the fidelity test is the single agreement mechanism.
  3. The **consumer generation surface**: `mkProjectShell`'s opt-in
     `hooks`/`hooksExcludes` arguments compose the definition's consumer
     profile with per-repo overrides, and git-hooks.nix's installation
     script (in the `shellHook`) installs the rendered
     `.pre-commit-config.yaml` — gitignored and regenerated on shell entry,
     upstream's recommended model. See `docs/MIGRATION.md` ("Customizing
     pre-commit hooks from the project flake") for the consumer contract,
     including the guarantee that a preserved hand-edited YAML is never
     overwritten (#878) and the planned `.vig-os` manifest opt-out flag
     (#885).

  Hooks that cannot run in the sandbox stay **runner-only** in the committed
  render and carry no gate profile in `nix/hooks.nix`: the generators
  `generate-docs`/`sync-manifest`, `pip-licenses` (reads `uv.lock`), `pymarkdown`
  (not in nixpkgs — also the one residual missing from the consumer generation
  profile), `no-commit-to-branch` and `destroyed-symlinks`
  (git-state-dependent), `check-agent-identity` (inspects the commit
  author/committer), and the `commit-msg`/`prepare-commit-msg`-stage hooks (never
  run by `--all-files`). `checks.pre-commit` is thus a Nix-verified guarantee that
  the pure hooks stay correct; the impure ones remain
  covered by CI's `prek run --all-files`. One fidelity note: the meta
  `debug-statements` hook parses the file's Python AST, so its `git-hooks.nix`
  package is pinned to the 3.14 `pre-commit-hooks` build to match the runner
  interpreter (PEP 758 parenthesis-free `except A, B:`), and `check-yaml` runs
  with `--allow-multiple-documents` in **both** the Nix check (git-hooks.nix'
  built-in hardcodes `--multi`) and the committed runner, so the two agree on
  multi-document YAML instead of the gate being more lenient than the runner.

### `libstdc++` for C-extension pre-commit hooks (#698)

Some pre-commit hooks run from pre-commit's **own** manylinux-wheel Python env
(not the project venv) and ship a C extension. The `pymarkdown` hook is the case
in point: its dependency `pyjson5` is a C extension linked against
`libstdc++.so.6`, which a NixOS host does not put on the loader path outside an
FHS environment — so the hook aborted with
`ImportError: libstdc++.so.6: cannot open shared object file` and forced
`--no-verify`. Unlike the standalone binaries in #697 (`ruff`/`typos`),
`pymarkdown` is **not** in nixpkgs, so the "add to `devTools` + `language:
system`" recipe does not apply.

`mkProjectShell` therefore **appends** `${pkgs.stdenv.cc.cc.lib}/lib` to
`LD_LIBRARY_PATH` in the dev-shell, so the wheel resolves the Nix C++ runtime.
That is the same `libstdc++` the Nix toolchain itself links, so the other
dev-shell binaries keep working (no version clash), and the existing
mkShell-injected `LD_LIBRARY_PATH` is appended to rather than clobbered. The fix
generalises to any future C-extension Python hook. A `nix-ld` host config
(`programs.nix-ld.enable` + `libraries = [ pkgs.stdenv.cc.cc ]`) would also work
but is per-contributor system config the repo cannot enforce, so it is at most a
fallback, not the fix.

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
git clone git@github.com:vig-os/devkit.git
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

### Image closures are cache-backed too (blocking push)

The cache is not just for the dev-shell. On the trusted paths the **image**
closure is pushed to `vig-os` Cachix as a **first-class, blocking** step (#776),
so published images are guaranteed cache-backed and consumers substitute the
closure instead of rebuilding it from source:

- `.github/actions/build-image` pushes the built `devcontainerImage` closure when
  its `push-image-closure` input is `true` (`nix path-info --recursive ./result |
  cachix push`). The release workflow (`build-and-test`) opts in, so every
  released image is cache-backed. The push is **blocking** (no
  `continue-on-error`) and guarded on a non-empty auth token, so per-PR CI stays
  **pull-only** and fork PRs (which lack the secret) never fail.
- The `Nix Image (discovery)` workflow pushes each per-arch image closure on
  `dev` as the same blocking step (distinct from the non-blocking GHCR discovery
  *tag* push).
- The release CVE gate also pushes the `devcontainerImageEnv` scan-target closure,
  so the vulnix scan surface is cache-backed as well.

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

The build pipeline is Nix-only (the Debian path was decommissioned in #642), and
the nightly `vulnix` gate is **blocking** — any unexcepted HIGH/CRITICAL finding
fails the scan. The remaining step is the deliberate Nix release that flips the
versioned/`:latest` publish, tracked in **issue #639**; the nightly `vulnix` gate
is the go/no-go signal for it.

## See also

- [`docs/rfcs/ADR-nix-devenv-strategy.md`](rfcs/ADR-nix-devenv-strategy.md) — why
  the org uses `pkgs.mkShell` + `nix-direnv` (not `devenv`/`devshell`), the
  three-axis framing (activation / shell definition / local services), and the
  `process-compose` + `services-flake` decision for local dev services.
- [`CONTRIBUTE.md`](../CONTRIBUTE.md) — onboarding fast path (clone → `direnv allow`).
- [`docs/NIX2CONTAINER.md`](NIX2CONTAINER.md) — the downstream production-image
  pattern with `nix2container` (distinct from this image's `buildLayeredImage`).
- [`docs/CONTAINER_SECURITY.md`](CONTAINER_SECURITY.md) — the full CVE-patching
  strategy (pinned `nixpkgs`, `vulnix`, SBOM/Trivy, exception registers).
- [`flake.nix`](../flake.nix) — the authoritative source for all of the above.
