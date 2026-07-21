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
  consumed as a flake input (`vigos.url = "github:vig-os/devkit"`).

The toolchain is defined once, in `flake.nix`'s `devTools` list. A parity test
guarantees the dev-shell and the image never drift. There is no second
dependency manifest (`requirements.yaml` is gone); to change the toolchain you
edit `devTools`, and to update it downstream you bump the flake input
(`nix flake update vigos`).

## The delivery modes

`install.sh … --mode <devcontainer|direnv|both|bare>` scaffolds a consumer for
one of four modes:

- **`devcontainer`** — a `.devcontainer/` that pulls the published image. The
  workspace is mounted; first-run `post-create.sh` sets up git/gh/pre-commit and
  runs `just sync`.
- **`direnv`** — a minimal `flake.nix` + `.envrc` stub. `direnv allow` (or
  `nix develop`) drops you into the shared toolchain on the host, no container.
  The stub is never overwritten on re-scaffold; update with `nix flake update`.
  The shipped `ci.yml` is the single **mode-aware** workflow
  ([#991](https://github.com/vig-os/devkit/issues/991)): in `direnv` mode it runs
  on the host runner, and the `setup-devkit-toolchain` composite installs Nix
  (with the vig-os Cachix substituter) and drives the same `just sync` /
  `just precommit` / `just test` contract inside the flake dev-shell. See
  [mode-aware CI](#mode-aware-ci) for how one file serves every mode.
- **`both`** — everything above (the default).
- **`bare`** — the standards layer only
  ([#885](https://github.com/vig-os/devkit/issues/885)): justfiles,
  `.pre-commit-config.yaml`, `.github/` CI, and `.vig-os` — no `.devcontainer/`,
  no `flake.nix`/`.envrc`. The tools come from
  the host (`uv`, `just`, `prek`), and the same mode-aware `ci.yml`
  ([#991](https://github.com/vig-os/devkit/issues/991)) runs on the host runner:
  the `setup-devkit-toolchain` composite sets up `uv` directly and drives the
  same `just sync` / `just precommit` / `just test` contract.

The chosen mode is persisted as `DEVKIT_MODE` in the `.vig-os` manifest (below),
so upgrades never need `--mode` again.

### Bare mode: `vig-utils` release console scripts

The release workflows invoke `prepare-changelog` and `renovate-changelog-pr`
(console scripts of `packages/vig-utils`). In `devcontainer`/`both` mode they
ship in the image; in `direnv` mode the flake dev-shell provides them (they are
on the toolchain SSoT, [#993](https://github.com/vig-os/devkit/issues/993)).
Bare mode has no flake and no image, so install them host-native with `uv`,
pinned to the same devkit version as `.vig-os`
(`DEVKIT_VERSION`/`DEVCONTAINER_VERSION`):

```bash
uv tool install "vig-utils @ git+https://github.com/vig-os/devkit@<DEVKIT_VERSION>#subdirectory=packages/vig-utils"
```

This puts `prepare-changelog`, `renovate-changelog-pr`, and the other
`vig-utils` scripts on PATH. Pin `<DEVKIT_VERSION>` to a release tag so the
tooling matches your `.vig-os` pin; the `setup-devkit-toolchain` composite
([#994](https://github.com/vig-os/devkit/issues/994)) runs this step for you in
bare-mode CI.

### Mode-aware CI

`ci.yml` is a single **mode-aware** workflow
([#991](https://github.com/vig-os/devkit/issues/991)) shipped identically to
every mode. A leading `resolve-toolchain` job reads `.vig-os` and outputs the
delivery `mode` and container `image` — the devcontainer image for
`devcontainer`/`both`, an **empty string** for `direnv`/`bare` (which makes the
downstream job run directly on the host runner, per
[the Option A ADR](rfcs/ADR-conditional-container-toolchain.md)). Each job then
declares `container: image: ${{ needs.resolve-toolchain.outputs.image }}` (with
an inert-on-host GHCR `credentials:` block) and calls the shared
`setup-devkit-toolchain` composite
([#994](https://github.com/vig-os/devkit/issues/994)) as its first step: the
in-image env + prek skew guard in container mode, `install-nix` + Cachix + the
flake dev-shell in `direnv`, or a `uv` host install in `bare`. After that
preamble the same `just sync|precommit|test` contract runs in every mode — no
per-mode overlay.

**Release/automation set is now mode-aware
([#991](https://github.com/vig-os/devkit/issues/991)):** the release and
automation workflows provision their toolchain the same way `ci.yml` does — a
leading `resolve-toolchain` job (or, in `prepare-release.yml`, the composite used
inline in the host `validate` job) selects the container image, **empty in the
`direnv`/`bare` modes so the job runs on the runner** (ADR Option A), and every
job runs the `setup-devkit-toolchain` composite as its toolchain preamble. They
are **no longer devcontainer-mode-only** — a host-mode consumer keeps them as-is,
with no per-mode deletion or disabling:

- `release.yml` (orchestrator) and its reusable `release-core.yml` /
  `release-publish.yml`, plus `prepare-release.yml`, `promote-release.yml`,
  `sync-issues.yml`, `renovate-changelog-build.yml`, `sync-main-to-dev.yml`
  — mode-aware via `resolve-toolchain` + `setup-devkit-toolchain`. The release
  choreography (step logic, ordering, inputs/outputs, rollback semantics) is
  unchanged; only toolchain provisioning became mode-aware.

Container-independent workflows keep working in every mode: `codeql.yml`,
`scorecard.yml`, `renovate-changelog-commit.yml`, and the project-owned,
host-native `release-extension.yml`.

`codeql.yml` and `scorecard.yml` additionally guard their analysis job with
`if: ${{ !github.event.repository.private }}`
([#1039](https://github.com/vig-os/devkit/issues/1039)): neither scan can succeed
on a private repo (CodeQL needs GitHub Advanced Security, unavailable on
Free-plan private repos; OpenSSF Scorecard is public-only), so private consumers
get a skipped (neutral) run instead of a permanently red one. A repo later
flipped public starts scanning automatically, with no re-scaffold.

### direnv mode: `shellHook` environment forwarding

In `direnv` mode the `setup-devkit-toolchain` preamble forwards your flake
dev-shell's `shellHook` environment to CI **by default**
([#1180](https://github.com/vig-os/devkit/issues/1180)). Any env var a project
exports from its `shellHook` (tool configuration, sensible defaults) is present
in every local `nix develop`/direnv session; before #1180 the preamble exported
only the dev-shell's `PATH` (via `GITHUB_PATH`), so those vars silently vanished
on CI — a local-vs-CI divergence that surfaced as unrelated tool errors
(a `shellHook`-seeded `OTTERDOG_TOKEN` placeholder worked locally and failed on
CI). The preamble now diffs the ambient runner environment against the dev-shell
environment (the `shellHook` has run inside `nix develop`) and writes the vars
the dev-shell **adds or changes** to `GITHUB_ENV`. The ambient diff is what keeps
host secrets — already in the runner env, unchanged inside the shell — out of
`GITHUB_ENV`; multi-line values are written with a random `GITHUB_ENV` heredoc
delimiter so they survive intact.

A denylist keeps shell-session state and Nix/stdenv build machinery from leaking
into the CI environment. Never forwarded:

- **Session/runtime shell state** — `PATH` (already handled via `GITHUB_PATH`),
  `HOME`, `USER`, `LOGNAME`, `SHELL`, `TERM`, `PWD`, `OLDPWD`, `SHLVL`, `IFS`,
  `TMPDIR`/`TMP`/`TEMP`/`TEMPDIR`.
- **Nix/stdenv build internals** — everything `NIX_*`; the stdenv scalars/lists
  `out`, `outputs`, `src`, `stdenv`, `system`, `builder`, `name`, `pname`,
  `version`, `shell`, `shellHook`, `buildInputs`, `nativeBuildInputs`,
  `propagatedBuildInputs`, `propagatedNativeBuildInputs`, `SOURCE_DATE_EPOCH`,
  `HOST_PATH`; and the build-machinery patterns `deps*`, `*Phase`, `phases`,
  `dont*`, `configureFlags`/`cmakeFlags`/`mesonFlags`/`makeFlags`, `patches`,
  `strictDeps`, `outputHash*`.

This is why the diff-plus-denylist approach is used instead of forwarding
`nix print-dev-env` wholesale: that dumps the full build machinery, none of which
belongs in a CI environment. Recipes should still avoid depending on env a
`shellHook` sets **only for interactive convenience** — CI parity is best-effort
for build machinery, but genuine `shellHook` exports are now forwarded.

## Workflow models

`install.sh … --workflow <gitflow|trunk>` selects a consumer's **branching
model** ([#1205](https://github.com/vig-os/devkit/issues/1205)), independently of
the delivery mode above. Empty/absent resolves to the `gitflow` default:

- **`gitflow`** (default) — a long-lived `dev` integration branch alongside
  `main`. `feature`/`bugfix` branches merge to `dev`, `release/X.Y.Z` is cut from
  `dev`, finalize merges to `main` + tags, and `sync-main-to-dev.yml` back-merges
  `main` into `dev`. This is the model existing consumers already run; nothing
  changes for them.
- **`trunk`** — no `dev` branch and no `sync-main-to-dev.yml`.
  `feature`/`bugfix`/`chore` branches merge straight to `main`. Releases are
  unchanged in every other respect: `release/X.Y.Z` is cut **from `main`**, run
  through the same RC/vulnix-gate/promote train, and **merged back into `main`**
  and tagged.

The model is realized entirely at scaffold time — an anchored `dev -> main` render
of the scaffolded workflows (`prepare-release`, `ci`, `codeql`, `sync-issues`),
the branch-naming skill, and the pre-commit branch guard, plus a
`sync-main-to-dev.yml` copy-exclude — mirroring how `DEVKIT_MODE` is applied and
with no runtime workflow logic (see
[`docs/rfcs/ADR-workflow-model.md`](rfcs/ADR-workflow-model.md) for the design and
[`docs/RELEASE_CYCLE.md`](RELEASE_CYCLE.md#workflow-models) for the topology). On a
fresh `trunk` install `init-workspace.sh` also skips creating the `dev` branch.

The chosen model is persisted as `DEVKIT_WORKFLOW` in the `.vig-os` manifest
(below) — **written back only for `trunk`**, so a `gitflow` `.vig-os` is
byte-for-byte unchanged — and upgrades never need `--workflow` again.

### Switching the workflow model

Like mode switching, **switching the workflow model never happens implicitly**,
and it is **destructive** in a way a mode switch is not: the scaffold renders
files, but it cannot reshape a repository's branch topology. An explicit
`--workflow` that contradicts the persisted `DEVKIT_WORKFLOW` **refuses** — inspect
the would-be change with `--preview` first, then, if you really mean it, set
`DEVKIT_WORKFLOW` in `.vig-os` yourself on a dedicated, clean upgrade branch (the
[preflight-guard flow](#upgrade-preflight-guard-and-preview)) and re-run the
upgrade.

- **`gitflow` → `trunk`:** after the re-scaffold drops the `dev`-referencing
  workflow content and prunes `sync-main-to-dev.yml`, the **remote `dev` branch is
  orphaned** — the scaffold does not (and must not) delete branches. Once no open
  work targets it, delete it manually: `git push origin --delete dev` (and
  `git branch -D dev` locally). Re-point any default-branch or branch-protection
  settings that named `dev` at `main`.
- **`trunk` → `gitflow`:** the re-scaffold restores the `dev`-based workflows and
  `sync-main-to-dev.yml`, but you must (re)create the `dev` branch yourself
  (`git branch dev main && git push -u origin dev`) for the gitflow release flow
  to work.

### Enable the dependency graph on new public consumers

The scaffolded `ci.yml` also ships a **Dependency Review** gate that blocks PRs
introducing known-vulnerable dependencies
([#1140](https://github.com/vig-os/devkit/issues/1140)). Like the scans above it
is guarded to public repos, because the dependency-graph API it reads is
unavailable on Free-plan private repos.

On a **public** repo the dependency graph is normally on by default — but the
`vig-os` org creates new repos with it **disabled**
(`dependency_graph_enabled_for_new_repositories: false`), so a fresh public
consumer's first Dependency Review run returns `403` until the graph is turned
on. Enable it once when provisioning a new public consumer (needs repo admin) —
the same idempotent endpoint the repo's *Settings → Security → Dependency graph*
toggle calls:

```bash
gh api -X PUT "repos/<owner>/<repo>/vulnerability-alerts"
```

This is a one-time, per-repo step run by no scaffold script, so it applies in
every delivery mode. A private consumer can skip it — the gate is neutral there
and starts working automatically if the repo is later flipped public
([#1166](https://github.com/vig-os/devkit/issues/1166)).

### Run CI on self-hosted runners

`ci.yml` defaults to GitHub-hosted `ubuntu-24.04` runners. A consumer whose org
runs its CI on self-hosted runners (e.g. GitHub billing blocks hosted runners
for heavy jobs) sets the optional `.vig-os` key `DEVKIT_CI_RUNNER` to a
**comma-separated runner label list** instead of hand-editing the
scaffold-managed workflow (hand-edits to `runs-on` are clobbered on the next
upgrade):

```ini
# .vig-os
DEVKIT_CI_RUNNER=self-hosted,linux,x64,meatgrinder
```

`resolve-toolchain` reads the key and emits a `runner-json` output — a JSON array
of the labels (`["self-hosted","linux","x64","meatgrinder"]`), or
`["ubuntu-24.04"]` when the key is absent — and the toolchain jobs (`lint`,
`test`, `commit-checks`) plus the `summary` gate declare
`runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}`. A single
label still emits a valid one-element array. The key is persisted across
re-scaffolds like the other manifest keys, so an upgrade preserves it with no
flags. Absent => unchanged behavior for every existing consumer
([#1173](https://github.com/vig-os/devkit/issues/1173)).

**Limitation — two jobs always stay hosted.** `resolve-toolchain` runs on the
hosted default because it *produces* `runner-json` (a job cannot depend on its
own output — chicken-and-egg); it is a seconds-long sparse checkout.
`dependency-review` also stays hosted: it is public-repo-only (skipped on private
repos), needs no toolchain, and reads GitHub's dependency-graph API. A consumer
whose org **cannot run any hosted job at all** therefore still needs those two
lanes handled separately (e.g. a repo-specific static render); this v1 keeps the
managed workflow minimal and does not cover that case.

### Point sync-issues at an unprotected mirror branch (protected `main`)

The scaffolded `sync-issues.yml` commits its regenerated issue/PR archive with a
**direct API push** to a target branch. That target is workflow-model-aware:
`dev` under `gitflow` (whose ruleset admits the commit App) and `main` under
`trunk`. On a `trunk` repo whose `main` carries a **require-PR ruleset** the
direct push is *refused* — `Changes must be made through a pull request` — so the
scheduled sync fails every run
([#1227](https://github.com/vig-os/devkit/issues/1227), first seen on
`vig-os/org-config`).

**Do not add the commit App as a ruleset bypass actor on `main`.** It is the
cheapest fix but was **rejected for security**: a bot that can write a protected
`main` can change whatever that branch controls (for `org-config`, the *applied*
organization configuration). Instead, set the optional `.vig-os` key
`DEVKIT_SYNC_TARGET` to a dedicated **unprotected mirror branch**:

```ini
# .vig-os
DEVKIT_SYNC_TARGET=sync/issue-mirror
```

The scaffolded job then **bootstraps** that branch from the default branch head
if it is absent (so its first run creates it) and pushes the archive there,
outside the `main` ruleset. The mirror branch **diverges permanently and is never
merged back** — every sync run regenerates the full issue/PR state from the
GitHub API, so the branch is a standalone, self-healing archive, not integration
work. Absent => the workflow-model default (`dev`/`main`), unchanged for every
existing consumer.

A second optional key, `DEVKIT_SYNC_SCHEDULE`, overrides the schedule trigger's
cron (validated as a 5-field cron at scaffold time; a protected-main mirror is
often paired with a lighter cadence):

```ini
# .vig-os
DEVKIT_SYNC_SCHEDULE=0 5 * * 0   # weekly, Sundays 05:00 UTC (default: 0 2 * * *)
```

Both keys are realized entirely at scaffold time — schedule triggers cannot take
inputs — and persisted across re-scaffolds like the other manifest keys, so an
upgrade preserves them with no flags. A malformed branch name or cron fails
loudly during `init-workspace.sh` rather than rendering a broken workflow
([#1228](https://github.com/vig-os/devkit/issues/1228)).

**Provisioning a new `trunk` consumer with a protected `main`:** set
`DEVKIT_SYNC_TARGET` to an unprotected mirror branch (above) — **not** a ruleset
bypass for the commit App.

**Deliberate exclusion — PR-based sync mode.** A variant where the sync job opens
a short-lived pull request into `main` (instead of pushing to a mirror) was
**evaluated and deferred** ([#1228](https://github.com/vig-os/devkit/issues/1228),
[#1227](https://github.com/vig-os/devkit/issues/1227) option (b)): the toil is
inherent against a review-requiring ruleset (a human approval per sync), its
safety value depends on ruleset state the knob cannot observe, and it needs
Renovate-class stale-PR machinery with zero live consumers asking for
human-gated sync. Revisit only when a consumer actually requests it.

## The `.vig-os` project manifest

Since [#885](https://github.com/vig-os/devkit/issues/885), `.vig-os` is
the project's declarative manifest, not just a version pin. Flat `KEY=VALUE`
lines with `#` comments; every consumer parses it line-based and ignores
unknown keys:

| Key | Meaning |
|-----|---------|
| `DEVCONTAINER_VERSION` | Scaffold/image version pin (managed by release automation; keeps its legacy name until the devkit rename, [#781](https://github.com/vig-os/devkit/issues/781)) |
| `DEVKIT_MODE` | Delivery mode: `devcontainer` \| `direnv` \| `both` \| `bare` |
| `DEVKIT_WORKFLOW` | Branching model: `gitflow` (default) \| `trunk`; written back only for `trunk` (see [Workflow models](#workflow-models), [#1205](https://github.com/vig-os/devkit/issues/1205)) |
| `DEVKIT_PROJECT` | Persisted project short name (`SHORT_NAME`) |
| `DEVKIT_ORG` | Persisted organization name (`ORG_NAME`) |
| `DEVKIT_REPO` | Persisted GitHub `owner/repo` (Renovate preset) |
| `DEVKIT_MODULES` | Reserved: space-separated capability modules mirroring `mkProjectShell`'s `modules = [ … ]` ([#884](https://github.com/vig-os/devkit/issues/884)) |
| `DEVKIT_CI_RUNNER` | Comma-separated runner label list for the scaffolded `ci.yml` toolchain jobs; empty (default) => the hosted `ubuntu-24.04` runner ([#1173](https://github.com/vig-os/devkit/issues/1173)) |
| `DEVKIT_SYNC_TARGET` | Branch the scaffolded sync-issues job commits to; empty (default) => the workflow-model default (`dev`/`main`). A protected-`main` consumer sets an unprotected mirror branch, e.g. `sync/issue-mirror` (see [Point sync-issues at an unprotected mirror branch](#point-sync-issues-at-an-unprotected-mirror-branch-protected-main), [#1228](https://github.com/vig-os/devkit/issues/1228)) |
| `DEVKIT_SYNC_SCHEDULE` | Cron override (5-field) for the sync-issues schedule trigger; empty (default) => the daily `0 2 * * *` ([#1228](https://github.com/vig-os/devkit/issues/1228)) |

How it behaves:

- **Precedence:** explicit flag/env > `.vig-os` value > prompt/default. The
  resolved values are written back on every (re)scaffold, so a manifest-bearing
  repo upgrades with `install.sh --force` and **no mode/identity flags** while
  keeping its shape and names. Note the behavior change: environment variables
  such as `SHORT_NAME` and `ORG_NAME` now suppress the corresponding
  interactive prompts entirely — the prompt only appears when neither a
  flag/env value nor a manifest value resolves the key.
- **Legacy consumers** (version-only `.vig-os`, or none) get their mode
  inferred conservatively on upgrade from the tree shape: a populated
  `.devcontainer/` plus `flake.nix`/`.envrc` widens to `both` (ambiguity always
  resolves to the wider mode, and the inference is printed; interactive runs
  confirm). The inferred mode is persisted, so the file self-documents from the
  first upgrade on. A repo is never reshaped on inference alone.
- **Mode switching never happens implicitly.** An explicit `--mode` that
  contradicts the persisted `DEVKIT_MODE` refuses: inspect the would-be change
  with `--preview` first, then either keep the persisted mode or set
  `DEVKIT_MODE` in `.vig-os` yourself on a dedicated, clean upgrade branch (the
  preflight-guard flow below) and re-run the upgrade.
- **Future flags live here.** The manifest is the home for upcoming per-project
  devkit switches (e.g. the raw-YAML hook opt-out planned in
  [#883](https://github.com/vig-os/devkit/issues/883)). `.vig-os` is a
  managed file: the devkit-known keys are re-read and written back on upgrade —
  do not park unrelated custom keys in it.

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
- **Python is CPython 3.14, uv-managed — but opt-in.** The image provides
  Python and `uv`, yet the scaffold itself is **language-neutral** and ships no
  `pyproject.toml`
  ([#929](https://github.com/vig-os/devkit/issues/929)); the `just`
  lint/format/test recipes no-op until one exists. Add a Python package layout
  with `nix flake init -t github:vig-os/devcontainer#python`
  ([#930](https://github.com/vig-os/devkit/issues/930)) or `uv init`. Once
  present, the project venv lives at `/root/assets/workspace/.venv` and is
  populated by `just sync` (`uv sync`).
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

2. **Native deps, `direnv` mode (preferred).** Enable the curated `native`
   capability module in the project flake
   ([#884](https://github.com/vig-os/devkit/issues/884), contract in
   [`docs/rfcs/ADR-capability-modules.md`](rfcs/ADR-capability-modules.md)):

   ```nix
   devShells.default = vigos.lib.mkProjectShell {
     inherit pkgs;
     modules = [ "native" ]; # stdenv.cc, cmake, gnumake, pkg-config + CC/CXX
   };
   ```

   The module is the shipped, tested equivalent of the hand-rolled
   `extraPackages = [ pkgs.stdenv.cc pkgs.cmake pkgs.gnumake pkgs.pkg-config ]`
   list (which still works and still wins PATH lookup over module packages if
   you need to override a tool). Inside `nix develop` / `direnv` the shell
   puts `cc`/`c++` on PATH and exports generic `CC`/`CXX`, so build backends
   find a real compiler regardless of what the image's baked interpreter
   recorded at image-build time (the image's sysconfig records are sanitized
   to the same generic names —
   [#879](https://github.com/vig-os/devkit/issues/879)). This path is
   field-validated by the 0.4.0 downstream runs
   ([#639](https://github.com/vig-os/devkit/issues/639)).

   Capability modules are a **dev-shell / direnv-mode feature only**: enabling
   one changes nothing about the published image, which stays base-only.
   `native` is the only module shipped today; `geant4`, `rust`,
   `fortran`/`f2py`, and `root` are named candidates gated on a concrete
   consumer ask.

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
   ([#854](https://github.com/vig-os/devkit/issues/854)) lands; #854
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
  modules = [ "native" ]; # compiler + generic build tools
  extraPackages = [
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

#### Overriding the Python interpreter for ABI alignment

`mkProjectShell` pins CPython 3.14 by default. A nixpkgs-provided package with a
compiled Python binding is built against **nixpkgs' own default CPython**, not
the devkit's 3.14 — so importing it from the 3.14 interpreter fails with an ABI
mismatch, and `extraPackages` alone cannot fix it (it adds the package to the
shell but cannot change the interpreter `uv` pins). Pass the matching
interpreter as `python` to align them
([#1038](https://github.com/vig-os/devkit/issues/1038)):

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  python = pkgs.python313; # match freecad's ABI (nixpkgs default CPython)
  extraPackages = [ pkgs.freecad ];
};
```

The override flows through the whole shell: `UV_PYTHON` (so `uv sync` builds the
venv against 3.13), and the bare `python`/`python3` on PATH. `pkgs.freecad`'s
`import FreeCAD` then works from the project venv. Omit the argument and the
shell is byte-identical to the pinned-3.14 default — this is a per-project escape
hatch for compiled nixpkgs bindings (FreeCAD today; Geant4/ROOT Python bindings
later), not a general downgrade knob.

#### Non-goal: a C/C++ toolchain in the base image

The published image will **not** ship gcc/cmake:

- it breaks the minimal-image stance and inflates every consumer, most of
  which never compile anything;
- it still would not suffice — real native builds also need third-party
  headers, libraries, and build config (see the Geant4 example above), which
  only a pinned project flake provides reproducibly.

The in-image behavior when no toolchain is provided is tracked in
[#879](https://github.com/vig-os/devkit/issues/879); the toolchain
itself always comes from one of the tiers above.

## Customizing pre-commit hooks from the project flake (opt-in)

Since [#883](https://github.com/vig-os/devkit/issues/883) the shared
hook set is defined once in the vigOS flake, and a consumer can compose it
from the **preserved** project `flake.nix` instead of hand-editing the
scaffolded `.pre-commit-config.yaml`:

> **`direnv` scaffolds opt in by default** ([#1167](https://github.com/vig-os/devkit/issues/1167)).
> A fresh `direnv` scaffold ships `flake.nix` with `hooks = { }` already active
> and no hand-managed `.pre-commit-config.yaml`, because the direnv CI lane runs
> on the bare host runner, where the flake-generated set — resolved entirely from
> the Nix store — is more robust than building the committed YAML's remote
> pre-commit repo hook envs per runner. Everything in this section still applies
> — customize via the `hooks`/`hooksExcludes` block; the generated config is a
> gitignored store symlink. `container`/`both` scaffolds keep the hand-managed
> YAML with the block commented out, and `bare` ships no flake at all.

```nix
devShells.default = vigos.lib.mkProjectShell {
  inherit pkgs;
  hooks = {
    pymarkdown.enable = false;                            # toggle a base hook
    detect-private-keys.excludes = [ "worker/src/index\\.ts" ];
    "no-commit-to-branch".settings.pattern = [ "^wip/.*$" ];
    my-data-check = {                                     # fully custom hook
      enable = true;
      entry = "./scripts/check-dat.sh";
      files = "\\.dat$";
      language = "system";
    };
  };
  hooksExcludes = [ "^data/stopping/" "\\.dat$" ];        # global excludes
};
```

The contract:

- **Opt-in only.** Without a `hooks`/`hooksExcludes` argument nothing changes:
  the dev-shell is byte-identical to before and your (preserved,
  [#878](https://github.com/vig-os/devkit/issues/878))
  `.pre-commit-config.yaml` stays the runner config, hand-managed by you.
- **Opting in makes the flake the generator.** On shell entry (a
  config-only snippet inside the `shellHook`) the rendered
  [git-hooks.nix](https://github.com/cachix/git-hooks.nix) config is
  installed as `.pre-commit-config.yaml` — a symlink into the Nix store. Add
  `.pre-commit-config.yaml` to `.gitignore`: it is a generated artifact now
  and regenerates on every toolchain bump.
- **`.githooks` stays the hook entry point — generation never rewires
  `core.hooksPath`.** Opting in only maintains the config symlink; it never
  touches `core.hooksPath` or installs anything into `.git/hooks`, so the
  scaffold's `.githooks` scripts (sanctioned-environment guard, any
  repo-owned additions) keep running all stages, and `.githooks/pre-commit`'s
  `prek run` picks the generated config up from the repo root. Opting back
  out leaves the git wiring untouched for the same reason.
- **A hand-edited file is never clobbered.** If a regular (non-symlink)
  `.pre-commit-config.yaml` exists, the installation script *refuses* and
  warns instead of overwriting. To complete the opt-in, port your
  customizations (global `exclude:`, per-hook `exclude:`) into the
  `hooks`/`hooksExcludes` block as above, then delete the YAML and gitignore
  it. To opt back out, remove the `hooks` argument and commit a plain YAML
  again.
- **`pymarkdown` is in the base set.** Since
  [#1170](https://github.com/vig-os/devkit/issues/1170) `pymarkdownlnt` is
  packaged in the flake and `pymarkdown` is a `language: system` base hook, so
  the generated set includes it — `direnv`/`bare` consumers gain markdown lint
  from the shared toolchain like `shellcheck`/`typos`. Toggle it off with
  `pymarkdown.enable = false` if a repo has no markdown to lint.
- The planned declarative `.vig-os` manifest
  ([#885](https://github.com/vig-os/devkit/issues/885)) will carry an
  explicit raw-YAML opt-out flag so the choice is recorded per-repo rather
  than inferred from the file state.

## Updating

- **Downstream dev environment:** `nix flake update vigos` (or re-run
  `install.sh --force` to refresh the scaffold; your `flake.nix`/`.envrc`/
  `pyproject.toml` and a populated `.devcontainer/` are preserved).
- **Toolchain versions / CVEs:** advance the pinned `nixpkgs` revision
  (Renovate's `nix` manager opens the PR); `flake.lock` is the controlling
  version document.

### Upgrade preflight guard and preview

An upgrade (`just devc-upgrade`, or `install.sh --force`) rewrites and deletes
files across the consumer tree, so the installer requires it to land on a
dedicated working branch as a single reviewable, revertible diff
([#886](https://github.com/vig-os/devkit/issues/886)):

- **Protected branches refuse** — `main`, `dev`, `release/*` (prefix), and a
  detached `HEAD`. On a protected branch with a clean tree the installer
  offers to create and switch to `chore/devkit-upgrade-<version>` for you;
  non-interactively it refuses with that command as the hint.
- **Dirty trees refuse** — `git status --porcelain` must be empty (staged,
  unstaged, or untracked-unignored changes all count; gitignored clutter such
  as `.venv/` does not). Commit or stash first.
- **Non-git directories warn** — there is no VCS safety net, so the installer
  asks for explicit confirmation before continuing.
- **`--skip-preflight` bypasses** both checks; `--smoke-test` runs and fresh
  installs (no `--force`) are exempt.

To see what an upgrade would change before running it, use `--preview`:

```bash
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
  | bash -s -- --force --preview .
```

It prints the add/overwrite/preserve/delete file report and exits without
touching the tree (unlike `--dry-run`, which only prints the container command
and computes no file report).

### Migrating a `devcontainer`/`both` repo to `direnv` or `bare`

By default a mode switch is **non-destructive** toward a populated pre-existing
`.devcontainer/`: switching a container repo to `direnv`/`bare` keeps the old
container next to the new flake ([#738](https://github.com/vig-os/devkit/issues/738)).
That is right for coexistence, but on a genuine **container → direnv/bare
migration** it strands a now-stale container. `--prune-devcontainer` opts into
removing it (`direnv`/`bare` modes only; rejected in `devcontainer`/`both`).

Because a mode switch never happens implicitly (see
[the `.vig-os` manifest](#the-vig-os-project-manifest) above), the migration is a
deliberate, reviewable branch:

1. On a clean upgrade branch, set `DEVKIT_MODE=direnv` (or `bare`) in `.vig-os`
   and commit it.
2. **Preview the cleanup first** — confirm the `.devcontainer/` moves into the
   `DELETED` listing (and nothing else you rely on does):

   ```bash
   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
     | bash -s -- --force --preview --mode direnv --prune-devcontainer .
   ```

3. Run the upgrade with the flag to apply it:

   ```bash
   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
     | bash -s -- --force --mode direnv --prune-devcontainer .
   ```

Interactive runs (no `--no-prompts`) that detect a populated pre-existing
`.devcontainer/` in a container-less mode prompt once
(`Prune existing .devcontainer/? (y/N)`, default No). Omit the flag entirely to
keep the #738 default and preserve the container.

## Upgrading an existing 0.3.x consumer — manual steps

`install.sh --version <X> --force` refreshes the scaffold and pins `<X>` in
`.vig-os`, but files you own are **preserved, not migrated**. Field-validated
checklist ([#859](https://github.com/vig-os/devkit/issues/859)) after the
re-scaffold:

1. **Base recipes moved into `justfile.project`** — 0.4.0 retired
   `.devcontainer/justfile.base`; `lint`/`format`/`precommit`/`test`/
   `test-cov`/`sync`/`update` now live in `justfile.project`, which is
   preserved on upgrade. The shipped `ci.yml` calls `just sync` /
   `just precommit` / `just test`, so the installer appends any of these
   recipes your preserved file does not already resolve (a clearly marked
   block, [#877](https://github.com/vig-os/devkit/issues/877)) and
   removes the stale `.devcontainer/justfile.base`. Review the appended
   block and fold it into your own recipes; also verify the root `justfile`
   still carries the scaffold `import?` lines — without them no layered
   recipe is reachable (the installer warns if the block is missing).
2. **`.pre-commit-config.yaml` is preserved on upgrade** — earlier upgrades
   replaced it wholesale, silently dropping repo-specific global and per-hook
   `exclude:` patterns (the autofix hooks then rewrote data files they must
   never touch, [#878](https://github.com/vig-os/devkit/issues/878)).
   The installer now keeps your file and prints a diff against the incoming
   template — review it and fold in the template evolution you want (e.g.
   `default_language_version`, runner-compat fixes, new hooks). It also warns
   if the preserved config does not parse under the shipped runner; check
   with `prek validate-config .pre-commit-config.yaml`.
3. **`pre-commit` invocations → `prek`** — the `pre-commit` binary is gone
   from the 0.4.0 image and venv; the hook runner is `prek` (a drop-in for
   `run`-style invocations, [#778](https://github.com/vig-os/devkit/issues/778)).
   Rename every invocation in files the upgrade preserves or your repo owns:
   the `justfile.project` `precommit` recipe (`uv run pre-commit run
   --all-files` → `prek run --all-files`), repo-managed `.githooks/` scripts
   beyond the scaffold-shipped three (e.g. a `pre-push` hook), hook `entry:`
   lines in `.pre-commit-config.yaml`, and CI configs. The installer scans
   the preserved surfaces and warns with `file:line`
   ([#881](https://github.com/vig-os/devkit/issues/881)). As a bridge,
   0.4.x images shipped a deprecated `pre-commit → prek` shim that printed a
   stderr notice; the one-cycle window is over and **0.5 images carry no
   `pre-commit` binary at all** ([#897](https://github.com/vig-os/devkit/issues/897))
   — unrenamed invocations now fail with exit 127, so act on the installer's
   scan warnings before committing. While editing old `.githooks`
   scripts, also change `#!/bin/bash` shebangs to `#!/usr/bin/env bash`:
   `/bin/bash` does not exist on NixOS hosts, so those hooks fail outside
   the container even after the rename. In CI, the reverse skew (an old scaffold
   still calling `pre-commit` against a new image, or a new scaffold on an image
   too old to ship `prek`) now surfaces as a one-line `::error::` from the
   `Verify toolchain (prek present)` guard step in the shipped `ci.yml` lint job
   ([#854](https://github.com/vig-os/devkit/issues/854)), instead of an
   opaque `exit 127` deep in the `just precommit` log.
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

## First release after migrating to devkit

The **first** release train a freshly migrated consumer runs has a one-time
sharp edge in the promote step. `promote-release.yml` is dispatched via
`workflow_dispatch`, and GitHub only registers a `workflow_dispatch` workflow
that exists on the **default branch**. `promote-release.yml` typically has no
pre-devkit counterpart on `main` (unlike `prepare-release.yml` / `release.yml`,
whose legacy filenames may collide and so stay dispatchable), and the thing that
puts it on the default branch is the release-PR merge that promote itself
performs. So on a first release:

```console
$ gh workflow run promote-release.yml -f version=X.Y.Z
HTTP 404: Workflow does not have 'workflow_dispatch' trigger (on the default branch)
```

Dispatching by numeric ID is impossible too — no run has ever registered the ID.
Once this first release lands (by the manual sequence below) the workflow is on
`main` and **every subsequent release promotes normally** with a plain
`gh workflow run promote-release.yml`.

> **The manual promote cannot be "resumed" by the workflow later.** Promote's
> validate job hard-requires a **still-draft** GitHub Release and an **open,
> approved** release PR. Once you undraft the Release and merge the PR by hand
> (below), those preconditions are gone, so a half-completed manual promote can
> never be finished by the registered workflow. Run the sequence through to the
> end in one go.

### First-release manual promote runbook

Prerequisites (produced by the final `release.yml` run): the git tag
`<prefix>X.Y.Z` exists, its **draft** GitHub Release exists, and the
`release/X.Y.Z → main` PR is open, approved, and CI-green. `<prefix>` is
`DEVKIT_TAG_PREFIX` (e.g. `v`), empty for bare `X.Y.Z` tags. Use a token with
`contents: write` on the repo (the Release App token, or an admin PAT).

1. **Publish (undraft) the GitHub Release** — the same `--draft=false` edit the
   `promote` job performs:

   ```bash
   gh release edit "<prefix>X.Y.Z" --draft=false
   ```

2. **Merge the release PR to `main`** — the `merge` job's step. This triggers
   `sync-main-to-dev`:

   ```bash
   gh pr merge "$(gh pr list --head release/X.Y.Z --base main --json number --jq '.[0].number')" --merge
   ```

3. **Best-effort RC cleanup** — delete the RC draft pre-releases and orphan git
   RC tags for this version, matching the `cleanup` job. Drafts delete by
   release id; tags with a surviving Release stay:

   ```bash
   # RC draft pre-releases (delete by id):
   gh api --paginate repos/$GH_REPO/releases \
     | jq -r --arg base "<prefix>X.Y.Z" \
         '.[] | select(.draft and .prerelease and (.tag_name | startswith($base + "-rc"))) | .id' \
     | xargs -rI{} gh api -X DELETE "repos/$GH_REPO/releases/{}"
   # Orphan git RC tags (no Release attached):
   git ls-remote --tags --refs origin "<prefix>X.Y.Z-rc*" | awk '{print $2}' | sed 's#refs/tags/##' \
     | xargs -rI{} gh api -X DELETE "repos/$GH_REPO/git/refs/tags/{}"
   ```

4. **Move the floating tags** (only if `DEVKIT_FLOATING_TAGS` is set). The Tag
   protection ruleset makes `<prefix>X` / `<prefix>X.Y` moves Release-App
   exclusive, so on a first release neither a human nor the (unregistered)
   workflow can move them without a one-off ruleset bypass — see
   [First-release floating tags](#first-release-floating-tags) below.

After step 2 the merged `main` carries `promote-release.yml`, so this whole
runbook is needed exactly once per consumer. See
[`docs/DOWNSTREAM_RELEASE.md`](./DOWNSTREAM_RELEASE.md) for the steady-state
(fully automated) release and promote flow.

### First-release floating tags

If your repo opts into floating tags (`DEVKIT_FLOATING_TAGS=major,minor` or a
subset), the imported **Tag ruleset bypasses only the Release App
(Integration)** — correct for steady state, where `promote-release.yml` moves
`<prefix>X` / `<prefix>X.Y` with the app token. But on a first release the
promote workflow is not dispatchable, and no human — **not even a repo/org
admin** — can create or move the floating tags against the ruleset:

```console
$ gh api -X PATCH repos/$GH_REPO/git/refs/tags/v0 -f sha=<commit> -F force=true
HTTP 422: Cannot update this protected ref
```

Left unmoved, the release publishes but `<prefix>X` still points at the previous
release and `<prefix>X.Y` is missing — silently breaking the advertised
`uses: owner/repo@<prefix>X` pin. The one-off bootstrap is to bypass the ruleset,
move the tags, then revert:

> **The same one-off recurs when a _new_ floating level first appears in steady
> state** ([#1157](https://github.com/vig-os/devkit/issues/1157)). Once the
> workflow is live it force-**updates** existing levels with the app token, but
> the first release of a new level must **create** the ref (`POST /git/refs`),
> and if the Tag ruleset does not bypass the Release App for its `creation` rule
> that create is denied — surfaced as the opaque `Reference does not exist`
> (HTTP 422). Example: a repo already carrying `<prefix>0` cuts its first
> `<prefix>0.Y` release. `promote-release.yml` now fails loud with a `::error::`
> naming the tag, target commit, and this remediation instead of a bare `gh`
> error. Apply the same bypass-create-revert below (using the **create** call in
> step 2), or grant the Release App a `creation` bypass so future levels move
> automatically.

1. **Temporarily grant repository admins a bypass.** In **Settings → Rules →
   Rulesets → (the Tag ruleset) → Bypass list**, add **Repository admin**
   (`RepositoryRole`, actor id `5`), then save. Equivalently via the API, append
   a bypass actor to the ruleset:

   ```bash
   gh api "repos/$GH_REPO/rulesets/<ruleset-id>" \
     --jq '.bypass_actors += [{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}] | {bypass_actors}' \
     | gh api -X PUT "repos/$GH_REPO/rulesets/<ruleset-id>" --input -
   ```

2. **Move the floating tags to the peeled release commit** — the same
   `move_tag` semantics as `promote-release.yml`. `release-publish.yml` creates
   an **annotated** tag, so peel it to the underlying commit first:

   ```bash
   PREFIX=v; VERSION=X.Y.Z            # DEVKIT_TAG_PREFIX and the release version
   REF=$(gh api "repos/$GH_REPO/git/ref/tags/${PREFIX}${VERSION}")
   SHA=$(printf '%s' "$REF" | jq -r '.object.sha')
   [ "$(printf '%s' "$REF" | jq -r '.object.type')" = tag ] && \
     SHA=$(gh api "repos/$GH_REPO/git/tags/$SHA" --jq '.object.sha')
   MAJOR=${VERSION%%.*}; MINOR=$(x=${VERSION#*.}; echo "${x%%.*}")
   # One call per level in DEVKIT_FLOATING_TAGS (major -> vX, minor -> vX.Y):
   for name in "${PREFIX}${MAJOR}" "${PREFIX}${MAJOR}.${MINOR}"; do
     gh api -X PATCH "repos/$GH_REPO/git/refs/tags/$name" -f sha="$SHA" -F force=true \
       || gh api "repos/$GH_REPO/git/refs" -f ref="refs/tags/$name" -f sha="$SHA"
   done
   ```

3. **Revert the ruleset** — remove the admin bypass you added in step 1, so the
   Tag ruleset is Release-App-exclusive again. This is the whole point of the
   "one-off": steady-state moves go back through `promote-release.yml`.

An alternative to the manual bypass is to ship a small **consumer-owned** dispatch
workflow that performs only the floating-tag move with the Release App token,
registered from day one of the migration — but the bypass-and-revert above needs
no new managed surface and is the recommended one-time path.

## The retired Debian line (historical)

The Debian build path was decommissioned in
[#642](https://github.com/vig-os/devkit/issues/642): the final
Debian-built release is **0.3.9**, and every release from 0.4.0 onward is
Nix-built. Released images are never deleted, so 0.3.9 remains pullable
(`DEVCONTAINER_VERSION=0.3.9` in the repo-root `.vig-os`), but the line is
frozen — it receives no CVE fixes and is not a supported rollback track.

## Upcoming rename: repository `devcontainer` → `devkit`

The **repository** is scheduled to be renamed to **`devkit`** in the release
cycle after the Nix cutover
([#781](https://github.com/vig-os/devkit/issues/781)). GitHub redirects the
old repository URL. The **published image is unchanged** — it stays
`ghcr.io/vig-os/devcontainer` (the artifact is a dev container; `devkit` is the
project that builds and ships it), so existing `.vig-os` pins and `podman pull`
commands keep working with no change. A re-scaffold (`install.sh --force`) only
refreshes the `install.sh` source URL and templated files; it does not change the
image you pull. The `.vig-os` version-pin key is `DEVKIT_VERSION` (the legacy
`DEVCONTAINER_VERSION` is still accepted).

**Existing `direnv`/`both` consumers: update the flake input by hand.** The
scaffolded `flake.nix` is a preserved file — a re-scaffold never overwrites it —
so a repo scaffolded before the rename keeps
`vigos.url = "github:vig-os/devcontainer"`. That URL keeps resolving via
GitHub's repository redirect, so nothing breaks, but new stubs now reference the
canonical `github:vig-os/devkit`. Update your input (and any pin-example comment)
to match, then `nix flake update vigos`:

```nix
vigos.url = "github:vig-os/devkit"; # was github:vig-os/devcontainer
```

### `DEVKIT_VERSION` and the pinned flake `ref` move in lockstep

If you **pin** the flake input to a release
(`vigos.url = "github:vig-os/devkit?ref=<tag>"`), the pinned `<tag>` and the
`DEVKIT_VERSION` written into `.vig-os` by the scaffold must stay on the **same
version**. They deliver **coupled halves of the same change**: the scaffold
(keyed to `DEVKIT_VERSION`, delivered by `install.sh --force`) writes files,
while the pinned flake input (`nix/hooks.nix`) delivers the matching hook
behavior. For example, the JSONC provenance banner
([#1053](https://github.com/vig-os/devkit/issues/1053)) is written by the
scaffold, but its compensating `check-json` exclude lives in the flake input —
bump only the scaffold and the strict `check-json` hook rejects the banner,
failing **every** commit
([#1093](https://github.com/vig-os/devkit/issues/1093)).

Keep them aligned: whenever a `--force` upgrade advances `DEVKIT_VERSION`, bump
the pinned `ref` to the same version and re-resolve the input:

```nix
vigos.url = "github:vig-os/devkit?ref=<new-DEVKIT_VERSION>";
```

```console
nix flake update vigos
```

A `--force` upgrade whose scaffold version differs from a pinned `vigos` ref now
prints a warning to that effect. A **floating** input
(`vigos.url = "github:vig-os/devkit"`, no `?ref=`) tracks the branch and needs no
manual bump — it is exempt.
