# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

- **Renovate: update `github-backup` from `==0.63.0` to `==0.64.0`** ([#960](https://github.com/vig-os/devcontainer/pull/960))
- **Renovate dependency update** ([#866](https://github.com/vig-os/devcontainer/pull/866))
  - Update `aquasecurity/trivy` from `v0.71.2` to `v0.72.0`
  - Update `astral-sh/setup-uv` from `v8.3.1` to `v8.3.2`
  - Update `docker/login-action` from `v4.2.0` to `v4.4.0`

- **Renovate: update `github/codeql-action` from `8aad20d` to `99df26d`** ([#862](https://github.com/vig-os/devcontainer/pull/862))

### Deprecated

### Removed

### Fixed

- **Nested scaffold docs dropped by unanchored preserve excludes** ([#953](https://github.com/vig-os/devcontainer/issues/953))
  - `init-workspace.sh` built its rsync preserve excludes as `--exclude=$name`, so bare `PRESERVE_FILES` entries (`README.md`, `CHANGELOG.md`) matched by basename at every depth and silently dropped devkit-authored nested docs (`.devcontainer/README.md`, `.devcontainer/CHANGELOG.md`, `.claude/skills/*/README.md`) on `--force` upgrades — files the `--preview` report still listed as ADDED. The excludes are now root-anchored (`--exclude=/$name`), matching `is_preserved_file`'s exact-path semantics: root docs stay preserved, nested docs ship.

- **Imageless `--no-prompts` defaulted the org to a bogus `vigOS/devc` literal** ([#954](https://github.com/vig-os/devcontainer/issues/954))
  - With no `ORG_NAME` env and no manifest `DEVKIT_ORG`, the org defaulted to the hardcoded `vigOS/devc` — a `/`-bearing value that sed-substituted into `{{ORG_NAME}}` in generated files (e.g. the LICENSE copyright line). The default now derives from the `GITHUB_REPOSITORY` owner segment (already resolved on this path via `DEVKIT_REPO`), falling back to the literal `vigOS` only when no usable owner/repo is present.

- **Broken links, duplicate sections, and name/title mismatches in agent skills** ([#912](https://github.com/vig-os/devcontainer/issues/912))
  - All `../../rules/*.mdc` links in `.claude/skills/` now point to the correct skill files or `CLAUDE.md` (`.claude/rules/` was removed in #626).
  - `../docs/RELEASE_CYCLE.md` links in `pr_create` and `pr_post-merge` corrected to `../../../docs/RELEASE_CYCLE.md`.
  - Duplicate `## Delegation` sections removed from `ci_check`, `worktree_ci-fix`, and `worktree_verify`.
  - `solve-and-pr` skill now launches `/worktree_solve-and-pr` (underscore, matching the real skill name).
  - `worktree_pr` PR title format aligned with `pr_create`: no manual issue number in title.
  - Obsolete `.claude/commands/` wrappers deleted (superseded by skills providing `/X` directly).

### Security

## [0.5.0](https://github.com/vig-os/devcontainer/releases/tag/0.5.0) - 2026-07-09

### Added

- **Opt-in Python starter flake template** ([#930](https://github.com/vig-os/devcontainer/issues/930))
  - `nix flake init -t github:vig-os/devcontainer#python` restores a Python package layout (`pyproject.toml`, `src/`, `tests/`) onto the now language-neutral scaffold ([#929](https://github.com/vig-os/devcontainer/issues/929)). The template uses a concrete `example_pkg` name the user renames — `nix flake init -t` does no placeholder substitution — and ships a minimal pytest dev group (no `science`/`jupyter` extras).

- **Authenticated GHCR pulls for the shipped container CI** ([#920](https://github.com/vig-os/devcontainer/issues/920))
  - The `resolve-image` action now runs an **authenticated** manifest probe: it logs in to `ghcr.io` before the probe when given a token (new optional `registry-token`/`registry-username` inputs) and no longer swallows the probe's stderr, so failures are classified into actionable `::error::` annotations that distinguish an auth/denied failure ("set the `GHCR_PULL_TOKEN` secret / grant `packages: read`") from a genuinely missing tag. The anonymous path is kept for public images.
  - Every shipped container job (`ci.yml`, `prepare-release.yml`, `promote-release.yml`, `release.yml`, `release-core.yml`, `release-publish.yml`, `sync-issues.yml`, `sync-main-to-dev.yml`, `renovate-changelog-build.yml`) gains an opt-in `credentials:` block (`username: github.actor`, `password: ${{ secrets.GHCR_PULL_TOKEN || github.token }}`) and `packages: read`, so a **private** or rate-limited image pulls without per-repo edits.
  - **Public consumers are unaffected:** with `GHCR_PULL_TOKEN` unset the expression falls back to the automatic `github.token` (never an empty password), which performs an authenticated pull of a public image successfully.
  - `docs/container-ci-quirks.md` re-framed from a "public-image limitation" note into first-class authenticated-pull documentation (secret contract, `github.token` fallback, `packages: read` requirement). Split out of the workflow audit ([#854](https://github.com/vig-os/devcontainer/issues/854)) and rides the devkit rename cycle ([#781](https://github.com/vig-os/devcontainer/issues/781)).

- **Nix-direct CI lane for direnv-mode consumers** ([#854](https://github.com/vig-os/devcontainer/issues/854))
  - `direnv` mode now scaffolds a host-native `ci.yml` overlay (`assets/workspace-direnv/`, applied like the bare overlay and keyed off the persisted `DEVKIT_MODE`): no `resolve-image`, no in-container jobs — the runner installs Nix (with the vig-os Cachix substituter, SHA-pinned `install-nix`/`cachix` actions reused from this repo's own lane) and drives the same `just sync|precommit|test` contract inside the flake dev-shell via `nix develop -c`, dropping the container-only `PREK_HOME`/`UV_PROJECT_ENVIRONMENT` env.
  - Documented boundary in `docs/MIGRATION.md` ("direnv-mode CI"): only `ci.yml` is converted for direnv mode; the other shipped workflows (`prepare-release`, `promote-release`, `release*`, `sync-issues`, `renovate-changelog-build`, `sync-main-to-dev`) stay container-based and devcontainer-mode-only until the full workflow audit rides the devkit rename ([#781](https://github.com/vig-os/devcontainer/issues/781)); the container-independent ones (`codeql`, `scorecard`, `renovate-changelog-commit`, `release-extension`) keep working in every mode.

- **Opt-in capability modules for `mkProjectShell`** ([#884](https://github.com/vig-os/devcontainer/issues/884))
  - `modules = [ "native" ]` composes curated capability modules (packages + env vars + shellHook fragments) onto the project dev-shell; contract recorded in `docs/rfcs/ADR-capability-modules.md`.
  - Zero-module shells are byte-identical to the previous builder and the published image stays base-only; `extraPackages` remains the per-repo escape hatch and wins PATH lookup.
  - `native` module ships first (`stdenv.cc`, `cmake`, `gnumake`, `pkg-config`, generic `CC`/`CXX`) — the long-term [#879](https://github.com/vig-os/devcontainer/issues/879) answer; `geant4`/`rust`/`fortran`/`root` stay ask-gated candidates.
  - Per-module flake checks (`checks.<system>.module-<name>`) plus a uv C-extension sdist smoke test (`tests/test_flake_modules.py`).

- **`.vig-os` project manifest and new `bare` delivery mode** ([#885](https://github.com/vig-os/devcontainer/issues/885))
  - `.vig-os` now persists the delivery mode and identity (`DEVKIT_MODE`, `DEVKIT_PROJECT`, `DEVKIT_ORG`, `DEVKIT_REPO`, reserved `DEVKIT_MODULES`) alongside the version pin — flat `KEY=VALUE` format unchanged, existing parsers byte-for-byte unaffected. Precedence flag/env > `.vig-os` > prompt/default, with resolved values written back, so manifest-bearing repos upgrade with `--force` and no mode/identity flags while keeping shape and names.
  - Legacy (version-only) consumers get their mode inferred conservatively from the tree shape on upgrade (wider mode on ambiguity, inference printed and persisted, never reshaping); an explicit `--mode` contradicting the persisted `DEVKIT_MODE` refuses, pointing at `--preview` and the preflight-guard flow.
  - New `bare` mode ships the standards layer only (justfiles, hooks config, `.github/` CI, `.vig-os`), prunes `.devcontainer/`/`flake.nix`/`.envrc` behind the #738/#859 pre-existence guards, and scaffolds a host-native `ci.yml` (no image resolution, no container jobs — `setup-uv` on the runner drives the same `just sync|precommit|test` contract) with `rust-just`/`prek` pinned to the toolchain versions.
  - The template `.vig-os` ships `DEVKIT_MODE` empty and the resolved mode/identity are persisted immediately after the template copy, so an upgrade aborted mid-scaffold can never persist a delivery mode the repo did not choose.

- **Preflight guard and diff preview for scaffold upgrades** ([#886](https://github.com/vig-os/devcontainer/issues/886))
  - `install.sh --force` upgrades now refuse on `main`/`dev`/`release/*`/detached HEAD and on a dirty tree, so every upgrade lands as a reviewable, revertible diff on a dedicated branch; on a protected branch with a clean tree the installer offers to create and switch to `chore/devkit-upgrade-<version>`, and non-git directories get a warn-and-confirm path. A single `--skip-preflight` flag bypasses the guard; `--smoke-test` runs and fresh installs are exempt.
  - New `--preview` mode prints the add/overwrite/preserve/delete file report (including mode-prune deletions such as the retired `.devcontainer/justfile.base`) and exits without changing any files — unlike `--dry-run`, which only prints the container command.

- **Flake-generated pre-commit hooks: one definition, consumer-extensible** ([#883](https://github.com/vig-os/devcontainer/issues/883))
  - `nix/hooks.nix` now defines the pre-commit hook set once; it renders the sandbox-pure `checks.pre-commit` gate, the committed `.pre-commit-config.yaml` + scaffold copy (drift CI-gated by `tests/test_flake_hooks.py` against `nix eval .#lib.hooksPortable` — the hand-synced triangle and the manifest transform chain are retired), and the consumer surface.
  - `mkProjectShell` gains opt-in `hooks` (toggle base hooks, per-hook `excludes`/overrides, fully custom hooks) and `hooksExcludes` (global excludes): entering the shell installs the rendered config as a repo-root symlink without ever touching `core.hooksPath` — the scaffold's `.githooks` entry point stays in charge; a preserved hand-edited YAML ([#878](https://github.com/vig-os/devcontainer/issues/878)) is never overwritten, and the zero-hooks dev-shell stays byte-identical.
  - Consumer contract and migration steps in `docs/MIGRATION.md`; the `.vig-os` manifest raw-YAML opt-out flag is tracked in [#885](https://github.com/vig-os/devcontainer/issues/885).

### Changed

- **Release-candidate dispatch gates on CI only** ([#902](https://github.com/vig-os/devcontainer/issues/902))
  - `release.yml` no longer requires the release PR to be marked ready-for-review and approved before publishing a candidate — candidate dispatch now gates on CI status only, so RCs are freely dispatchable during verification while the PR stays a draft.
  - The draft + approval gate now applies only to the **final** release (the step that burns the immutable `X.Y.Z` tag); `promote-release.yml`'s merge job still re-enforces approval before merging to `main`, so `main` and `:latest` remain fully protected.
  - Release docs, `justfile`, and `CONTRIBUTE.md` reordered accordingly: publish candidates to verify first, then mark ready and get approval before `finalize-release`.

- **Copied scaffold is language-neutral** ([#929](https://github.com/vig-os/devcontainer/issues/929))
  - The scaffold no longer assumes a Python package: `just lint/format/test/test-cov` are guarded on `pyproject.toml` and no-op (exit 0) when it is absent, mirroring the existing `sync` guard, so a non-Python repo's `just sync|precommit|test` CI contract stays green out of the box.
  - `init-workspace.sh` drops the `src/template_project` → `src/<name>` rename and test-import rewrite; `pyproject.toml` stays in the preserved set, so a consumer that brings its own is never clobbered.

### Removed

- **`pre-commit` compat shim removed from the image** ([#897](https://github.com/vig-os/devcontainer/issues/897))
  - The one-release-cycle `pre-commit → prek` shim shipped in 0.4.x ([#881](https://github.com/vig-os/devcontainer/issues/881)) is gone; `pre-commit` invocations now fail with exit 127.
  - Consumers had the 0.4.x cycle to rename invocations; the upgrade-time scan still warns with `file:line` on preserved surfaces — see `docs/MIGRATION.md` for the rename checklist (justfile recipes, repo-owned `.githooks/`, CI configs → `prek`).

- **Python package starter dropped from the scaffold** ([#929](https://github.com/vig-os/devcontainer/issues/929))
  - `pyproject.toml`, `src/template_project/`, and `tests/` are no longer shipped in `assets/workspace/`; a fresh scaffold is language-neutral. Restore a Python layout on demand with the opt-in `nix flake init -t github:vig-os/devcontainer#python` template ([#930](https://github.com/vig-os/devcontainer/issues/930)).

### Fixed

- **Upgrade preview report follows template symlinks** ([#949](https://github.com/vig-os/devcontainer/issues/949))
  - On the Nix image the baked template is a tree of symlinks into the nix store, so the `--preview`/`--force` classifier's `find … -type f` matched zero files and the OVERWRITTEN/ADDED report was always empty even though the real copy (`rsync -avL`) still overwrote them. The classifier now uses `find -L` to follow symlinks and match the copy semantics.

- **Upgrade preview no longer over-reports the baked `.venv` tree** ([#951](https://github.com/vig-os/devcontainer/issues/951))
  - Follow-up to the [#949](https://github.com/vig-os/devcontainer/issues/949) preview fix: `find -L` also descended the baked `.venv` symlink tree, so the ADDED section listed phantom `.venv/…/site-packages/*` files the real upgrade never writes. The report `find` now mirrors the static excludes the rsync copy applies (`.venv`, `docs/issues/`, `docs/pull-requests/`), so ADDED matches what the upgrade actually does.

- **Autochangelog now records grouped Renovate PRs** ([#936](https://github.com/vig-os/devcontainer/issues/936))
  - `renovate-changelog-pr` parsed the update table only when the change cell used an ASCII `->` arrow, but Renovate renders it with the Unicode arrow `→` (U+2192). Every real Renovate PR body therefore parsed to nothing; a changelog entry only appeared when the PR *title* happened to match (digest bumps, single `update X to Y`), so grouped dependency PRs were silently skipped. The change-cell parser now accepts both arrows.

- **Imageless upgrades stamp the real built tag** ([#921](https://github.com/vig-os/devcontainer/issues/921))
  - The image now bakes an authoritative built-tag record (`/root/assets/VERSION`) distinct from the template `.vig-os` pin: the release `build-image` action runs `nix build --impure` with `VIG_OS_VERSION` set to the true publish tag (RCs included), which the flake reads via `builtins.getEnv`. A plain, pure `nix build` reads `""` and falls back to the checked-in repo pin, so ordinary builds stay bit-reproducible.
  - `init-workspace.sh` reads that record when no `VIG_OS_VERSION` is forwarded, so a bare `podman run … init-workspace.sh` upgrade (no `install.sh`) now pins `.vig-os` to the image's real tag instead of the stale baked template pin ([#916](https://github.com/vig-os/devcontainer/issues/916)); an explicit `VIG_OS_VERSION` still wins, and an absent record leaves the pin untouched.

- **Template `sync` recipe no longer forces `--all-extras`** ([#892](https://github.com/vig-os/devcontainer/issues/892))
  - The shipped `justfile.project` `sync` recipe used `uv sync --all-extras --all-groups`, which forced every optional extra to install. Repos that quarantine platform-limited dependencies (e.g. cp312/cp313-only wheels) in extras got a hard `just sync` failure on the cp314 image.
  - The recipe is now parameterized (`sync *args="--all-groups"`) and defaults to `--all-groups`: dev groups stay synced while extras become opt-in via `just sync --all-extras`. The `update` recipe (which calls `just sync`) uses the new default unchanged.

- **Version-skew hardening for the shipped CI glue** ([#854](https://github.com/vig-os/devcontainer/issues/854))
  - **CI-wired skew guard:** the shipped container `ci.yml` and the new direnv `ci.yml` lint jobs now fail fast with an actionable `::error::` if the toolchain does not provide `prek`, turning an opaque `just precommit` exit 127 (old scaffold vs new image, or an image too old to ship the prek hook runner) into a one-line diagnosis.
  - **`prepare-release.yml` resolver unified:** the scaffold's forked inline-awk image resolver with a silent `latest` fallback is replaced by the shared `resolve-image` action, which hard-fails on a missing/unreadable `DEVCONTAINER_VERSION` pin.
  - **`devc-upgrade` honors the pin:** the recipe read `install.sh` from `main` regardless of the consumer's pin; it now reads `DEVCONTAINER_VERSION` from `.vig-os` and upgrades to that generation (script ref + `--version`), keeping `main`/`latest` only for unpinned repos.
  - **pipefail in every mode:** `set shell := ["bash", "-euo", "pipefail", "-c"]` moved from the devc-only `justfile.devc` to the root `justfile` (the SSoT), so direnv/bare recipes get pipefail too.
  - **`init-precommit.sh` derives its root** from the script location instead of a hard-coded `/workspace/{{SHORT_NAME}}`.
  - **Stale doc fixed:** `docs/container-ci-quirks.md` no longer describes a removed `uv run bandit` `pre-commit` hook; the private-image (unauthenticated `resolve-image` probe + missing `credentials:`) limitation is documented, with the first-class fix tracked in [#920](https://github.com/vig-os/devcontainer/issues/920).

### Security

- **Accept the curl 8.20.0 advisory batch in the vulnix register pending a patched upstream release** ([#941](https://github.com/vig-os/devcontainer/issues/941))
  - The 2026-06-24 curl disclosure added 17 HIGH/CRITICAL CVEs against curl 8.20.0 to the vulnix feed (four CVSS 9.8 — an HTTP/2 stream-dependency-tree UAF, a cross-origin Digest auth-state leak, a SASL double-free, and a stale proxy-password leak — plus a CVSS 9.1 batch and further HIGHs); they surfaced 2026-07-08 and blocked the 0.5.0-rc1 publish at the release vulnix gate. curl is reachable in the image (https/git-over-https, flake fetches, the docker→podman shim), so this is a time-boxed risk acceptance, not a dismissal.
  - No fixed curl exists to advance to: 8.20.0 is the newest release upstream and in both `nixos-26.05` and `nixpkgs-unstable`, so the "advance the rev" lever has nowhere to land. Added a short-dated `.vulnixignore` exception (expires 2026-07-22) to unblock the gate; the block is dropped and the pin advanced once Renovate's `nix` manager surfaces a patched curl.

## [0.4.1](https://github.com/vig-os/devcontainer/releases/tag/0.4.1) - 2026-07-08

### Added

- **ADR: terminal home environment as devkit home-manager modules** ([#815](https://github.com/vig-os/devcontainer/issues/815))
  - Accepted `docs/rfcs/ADR-home-environment-modules.md`: parameterized `vigos.*` home-manager modules as a second product of this repo (epic [#814](https://github.com/vig-os/devcontainer/issues/814)).

- **Home-manager module release/versioning policy** ([#816](https://github.com/vig-os/devcontainer/issues/816))
  - `docs/NIX.md`: modules ride the existing release train (consumers pin tags), `mkRenamedOptionModule` deprecation shims, dogfood-canary exception, and the `#### Modules` changelog sub-heading convention.
  - Workspace scaffold `vigos.url` float is now documented as deliberate, with the pin recipe.

- **Scheduled nixpkgs-unstable lock bump** ([#817](https://github.com/vig-os/devcontainer/issues/817))
  - Weekly workflow refreshing the fast-movers pin (uv, gh, claude-code) via a chore PR to dev, gated by full CI.

- **vigos.* home module set + homeConfigurations matrix** ([#818](https://github.com/vig-os/devcontainer/issues/818), [#819](https://github.com/vig-os/devcontainer/issues/819))
  - `homeManagerModules.{default,packages,shell,multiplexer,cli,direnv,git}` exported as path modules (+ `homeModules` alias); `home-manager` flake input (release-26.05, nixpkgs follows); `ci-{minimal,full}` homeConfigurations across 4 systems built as Tier-0 `hm-*` checks (x86_64-darwin eval-only).

- **Home Matrix CI workflow** ([#820](https://github.com/vig-os/devcontainer/issues/820))
  - Builds the ci homeConfigurations on aarch64-darwin (macos-latest) and aarch64-linux and pushes closures to Cachix; separate non-required workflow (fail-soft by status).

- **vigos.shell module** ([#821](https://github.com/vig-os/devcontainer/issues/821))
  - Bash + zsh, starship, atuin, zoxide under one enable flag; opt-in secretsEnv hook exporting ~/.config/vigos/secrets/<NAME> per the ADR credentials interface.

- **vigos.multiplexer, vigos.cli, vigos.direnv modules** ([#821](https://github.com/vig-os/devcontainer/issues/821))
  - tmux org defaults (vi keys, sane scrollback), modern-unix config (bat/eza/fzf/ripgrep/fd — configuration only, packages stay in vigos.packages), direnv + nix-direnv.

- **vigos.git module** ([#821](https://github.com/vig-os/devcontainer/issues/821))
  - git + delta, gh (ssh protocol), lazygit; identity and per-user-x-host SSH signing are null-default options — nothing is written unless set, so fresh hosts never fail their first commit.

- **templates.personal + homeConfigurations.demo** ([#827](https://github.com/vig-os/devcontainer/issues/827))
  - `nix flake init -t github:vig-os/devcontainer#personal` scaffolds a personal home-manager flake on the vigos.* modules; `demo` is the full-profile reference configuration.

- **Home environment docs** ([#825](https://github.com/vig-os/devcontainer/issues/825), [#826](https://github.com/vig-os/devcontainer/issues/826))
  - docs/home/: bootstrap guide (installer, macOS trusted-users trap, first activation), override cookbook, rollback table, best-effort Intel meaning, credential-hygiene runbook.

- **CLAUDE.md hierarchy templates** ([#828](https://github.com/vig-os/devcontainer/issues/828))
  - docs/home/claude-md/: user-global, workspace-root, and workspace layer templates + the directory-layout convention that makes the cascade work. Guidelines, not enforcement.

- **vigos.claude module + container secrets path** ([#823](https://github.com/vig-os/devcontainer/issues/823), absorbs [#546](https://github.com/vig-os/devcontainer/issues/546))
  - ~/.claude policy per the ADR: settings.json seeded copy-if-absent (org seed pre-authorizes nothing, includeCoAuthoredBy=false), managed vigos.md fragment (checksum-overwrite + .bak), @vigos.md import line seeded into the user-owned CLAUDE.md, DISABLE_AUTOUPDATER via sessionVariables, optional workspace-CLAUDE.md management (empty by default).
  - Devcontainer scaffold mounts ~/.config/vigos/secrets read-only and exports the files as env vars at shell startup — the slim token path replacing setup-claude.sh forwarding.

- **vigos.sesh, vigos.ghdash, vigos.editor modules** ([#824](https://github.com/vig-os/devcontainer/issues/824))
  - sesh project sessions with a parameterized standard tmux layout (sessions + layout.windows options, no hardcoded paths), gh-dash with scoped lean sections via repoFilters, neovim with the claudecode.nvim bridge (plain programs.neovim, no nixvim input).

### Changed

- **Renovate: update `numpy` to `v2.5.1`** ([#865](https://github.com/vig-os/devcontainer/pull/865))

- **MIGRATION.md: formalized the native-build contract** ([#882](https://github.com/vig-os/devcontainer/issues/882))
  - Tiered policy for native Python builds (wheel-only / toolchain from the project flake via `mkProjectShell.extraPackages` / in-container `nix develop -c` middle path), a worked Geant4/ROOT example, and the explicit non-goal of shipping a C/C++ toolchain in the base image. Cross-links [#879](https://github.com/vig-os/devcontainer/issues/879) and [#854](https://github.com/vig-os/devcontainer/issues/854).

#### Modules

- **homeManagerModules.default is now the umbrella** importing every `vigos.*` module, each disabled by default ([#818](https://github.com/vig-os/devcontainer/issues/818)); existing imports keep working unchanged.

### Deprecated

#### Modules

- **`programs.vigos-devtools.enable`** → `vigos.packages.enable` ([#818](https://github.com/vig-os/devcontainer/issues/818)); a `mkRenamedOptionModule` shim keeps the old option working for one release (docs/NIX.md policy).

### Removed

- **Documented Debian fallback retired** ([#642](https://github.com/vig-os/devcontainer/issues/642))
  - The build has been Nix-only since 0.4.0; docs and workflow comments no longer present the Debian image as a rollback path. Pinning the frozen 0.3.9 release remains possible but unsupported.

### Fixed

- **Preserve a customized `.typos.toml` on upgrade** ([#913](https://github.com/vig-os/devcontainer/issues/913))
  - `.typos.toml` joins the preserved-file set so a consumer's spell-check exceptions survive a `--force` upgrade; the upgrade prints the template diff (like `.pre-commit-config.yaml`, [#878](https://github.com/vig-os/devcontainer/issues/878)). Previously the generic template overwrote it and the `typos` hook then "corrected" real content.
  - A consumer carrying the legacy `_typos.toml` no longer also receives the template `.typos.toml`, avoiding two active typos configs.

- **Render preserved-file diff previews with `git diff`** ([#916](https://github.com/vig-os/devcontainer/issues/916))
  - The preserved-file upgrade preview called `diff`, which the image does not ship, printing `command not found` into an empty box; it now uses `git diff --no-index`.

- **Scan preserved CI workflows for the retired `pre-commit` binary** ([#916](https://github.com/vig-os/devcontainer/issues/916))
  - The upgrade reference scan ([#881](https://github.com/vig-os/devcontainer/issues/881)) now also covers preserved `.github/workflows/*.yml`, flagging real `pre-commit` invocations with `file:line` while ignoring comments and step `name:` descriptions.

- **Resolve the GitHub origin before scaffolding the workspace** ([#916](https://github.com/vig-os/devcontainer/issues/916))
  - Under `--no-prompts`, a missing or underivable origin now aborts before any files are copied, instead of leaving a half-scaffolded workspace mid-run.

- **Namespace scaffold `justfile.gh` git helpers to prevent consumer recipe collisions** ([#915](https://github.com/vig-os/devcontainer/issues/915))
  - Renamed the shipped git-helper recipes `log` → `gh-log` and `branch` → `gh-branch` (matching the `gh-issues` convention). A consumer whose preserved `justfile.project` defined its own `log`/`branch` recipes previously hit a hard `just` parse failure (`recipe log … is redefined`) after upgrade, making `just` unusable and silently disabling the [#877](https://github.com/vig-os/devcontainer/issues/877) base-recipe repair.
  - **Migration:** consumers who scripted against the shipped `just log` / `just branch` recipes must switch to `just gh-log` / `just gh-branch`; consumers who defined their own `log`/`branch` now keep them without collision.

- **Renovate changelog template no longer leaks the upstream `assets/workspace` mirror** ([#914](https://github.com/vig-os/devcontainer/issues/914))
  - The synced consumer `renovate-changelog-build.yml`/`-commit.yml` copied the `assets/workspace/.devcontainer/CHANGELOG.md` mirror plumbing verbatim; consumers have no such tree, so the steps hard-failed under `set -euo pipefail` on every Renovate changelog run. Manifest transforms now strip the mirror copies, leaving the template touching only the consumer's own `CHANGELOG.md`.

- **Scaffold upgrade strands base recipes in a preserved `justfile.project`** ([#877](https://github.com/vig-os/devcontainer/issues/877))
  - 0.4.0 moved `lint`/`format`/`precommit`/`test`/`test-cov`/`sync`/`update` into `justfile.project`, which is preserved on upgrade — 0.3.x consumers never received them and the shipped `ci.yml` failed with `justfile does not contain recipe 'sync'`. `init-workspace --force` now appends the missing base recipes from the template into the preserved file (customized recipes always win; idempotent).
  - The retired `.devcontainer/justfile.base` is removed on upgrade where the scaffold manages `.devcontainer/` (never in `direnv` mode, [#738](https://github.com/vig-os/devcontainer/issues/738)), and the installer warns if the root `justfile` lacks the scaffold `import?` block.

- **Renovate changelog artifact drops the workspace mirror; `metadata.env` breaks on parenthesized branches** ([#874](https://github.com/vig-os/devcontainer/issues/874))
  - `upload-artifact` silently excluded the mirror under the hidden `.devcontainer` directory, so the bot commit updated only the root `CHANGELOG.md` and tripped the `sync-manifest` gate; now uploaded with `include-hidden-files: true`.
  - `metadata.env` values are `%q`-quoted so grouped Renovate branch names (e.g. `renovate/python-(minor-and-patch)`) survive being `source`d by the commit workflow.

- **Renovate changelog entries land as plain `### Changed` bullets, not under `#### Modules`** ([#867](https://github.com/vig-os/devcontainer/issues/867))
  - `renovate-changelog-pr` appended entries at the bottom of the `### Changed` block, so with the `#### Modules` sub-heading convention ([#816](https://github.com/vig-os/devcontainer/issues/816)) a dependency bump was filed beneath `#### Modules` and read as a module change. Entries now insert at the top of `### Changed`, above any `####` sub-heading, with Keep-a-Changelog spacing preserved.

- **Image Python advertised the phantom Nix build toolchain (`gcc`/`g++`) in sysconfig** ([#879](https://github.com/vig-os/devcontainer/issues/879))
  - The baked CPython recorded its nixpkgs build compilers in `sysconfig` (`CC`/`CXX`/`LINKCC`/`LDSHARED`/`BLDSHARED`/`LDCXXSHARED`), but the image ships no compiler — PEP 517 backends inherited the phantom names verbatim: scikit-build-core exports `CC`/`CXX`, so CMake hard-failed on the missing `g++` instead of discovering the project-flake toolchain on `PATH`, and setuptools invoked the literal `gcc`.
  - The image build now sanitizes the baked `_sysconfigdata*.py` / `_sysconfig_vars*.json` / config `Makefile` first tokens to the generic POSIX `cc`/`c++`, restoring `PATH` compiler discovery. Implemented as a shadow copy in the final image layer — no CPython rebuild, dev-shell toolchain untouched, and the no-compiler-baked consumer contract stands (documented via [#882](https://github.com/vig-os/devcontainer/issues/882)).

- **Scaffold upgrade replaces `.pre-commit-config.yaml`, silently clobbering repo-specific hook config** ([#878](https://github.com/vig-os/devcontainer/issues/878))
  - The upgrade overwrote the consumer's `.pre-commit-config.yaml` wholesale, dropping the repo-specific global `exclude:` block and per-hook `exclude:` keys — the hook suite then rewrote data files it must never touch and false-flagged PEM marker literals. The file is now preserved on upgrade (like `justfile.project`, [#877](https://github.com/vig-os/devcontainer/issues/877)).
  - Because template hook-stack evolution no longer arrives automatically, `init-workspace --force` prints a diff of the preserved file against the incoming template so consumers can fold changes in deliberately, and warns (non-fatally) when the preserved config does not parse under `prek validate-config` — a config the runner cannot load breaks every commit in the new image.

- **`pre-commit` binary dropped without a compat path — preserved consumer recipes and `.githooks` calling it break** ([#881](https://github.com/vig-os/devcontainer/issues/881))
  - The 0.4.0 image retired the Python `pre-commit` for `prek` ([#778](https://github.com/vig-os/devcontainer/issues/778)), but files preserved on upgrade still invoke it and exit 127 (field-validated on a 0.3.5 → 0.4.0 consumer: the preserved `justfile.project` `precommit` recipe and repo-managed `.githooks` scripts broke every commit). The image now ships a **deprecated one-cycle `pre-commit → prek` shim** (stderr notice, removed in 0.5) so consumer hook scripts keep working while they migrate.
  - `init-workspace --force` scans the post-scaffold `justfile.project`, `.githooks/` scripts and `.pre-commit-config.yaml` for invocation-shaped `pre-commit` references and warns (non-fatally) with `file:line`, pointing at the MIGRATION.md rename checklist — which now also covers the NixOS `#!/bin/bash` shebang gotcha in old-scaffold `.githooks`.

### Security

- **Accept podman `CVE-2026-57231` in the vulnix register pending the nixpkgs 26.05 backport** ([#905](https://github.com/vig-os/devcontainer/issues/905))
  - podman 5.8.2 (affects 5.8.1–5.8.3) leaks matching host environment variables into a container when a malicious image manifest carries malformed `Env` entries (a key with no value, via the `*` glob) — CVSS 7.5, a supply-chain risk only when running untrusted images. The release CVE gate blocked the 0.4.1 RC on this finding.
  - Fixed upstream in 5.8.4/6.0.0, but the pinned `nixpkgs` `release-26.05` still ships 5.8.2 (backport [NixOS/nixpkgs#536367](https://github.com/NixOS/nixpkgs/pull/536367) open), so advancing the rev cannot remediate yet. Added a short-dated `.vulnixignore` exception (expires 2026-08-06, re-check weekly) to unblock the gate; the exception flips to a nixpkgs rev-advance once the backport lands.

## [0.4.0](https://github.com/vig-os/devcontainer/releases/tag/0.4.0) - 2026-07-06

### Added

- **Shared `mkProjectServices` local-services helper (process-compose + services-flake)** ([#795](https://github.com/vig-os/devcontainer/issues/795))
  - New `lib.mkProjectServices` output implementing the local-services axis of [ADR-nix-devenv-strategy](docs/rfcs/ADR-nix-devenv-strategy.md): declared [`services-flake`](https://github.com/juspay/services-flake) modules become a daemonless [`process-compose`](https://github.com/F1bonacc1/process-compose) stack — `nix run .#services` boots native-process services with **no Docker/Podman daemon**, versions from the pinned `nixpkgs` lock (no out-of-lock image tags), and zero extra flake inputs downstream (both service flakes resolve from this flake's lock as dependency-free leaf entries)
  - This flake carries the validating PoC: `nix run .#services` boots **SeaweedFS (S3) + Postgres**, asserted end-to-end (boot, health probes, teardown, no container fixtures) by the new `tests/test_flake_services.py`. The issue named MinIO, but nixpkgs marks `minio` abandoned upstream with unfixed CVEs, so the PoC ships the maintained S3-compatible SeaweedFS instead (recorded in `docs/NIX.md` and on the issue)
  - The flake-parts question is resolved without adopting it: `mkProjectServices` uses `process-compose-flake`'s standalone `evalModules` (services-flake's documented no-flake-parts path), so the flake stays on `flake-utils`. Measured cost recorded in `docs/NIX.md` (~0.8 s eval / ~3 s boot-to-healthy vs devenv's ~165 s IFD)
  - The scaffold opts consumers in but never forces them: the flake stub documents a commented `packages.services` block and `justfile.project` ships a commented `services` recipe — both preserved-on-upgrade files, so existing consumers are untouched
- **Flake checks as CI Tier 0 (nix-fast-build)** ([#779](https://github.com/vig-os/devcontainer/issues/779))
  - The `project-checks` CI job now builds every `checks.<system>` derivation (treefmt formatting, deadnix/statix, dev-shell build, `devShellTools`, and the git-hooks.nix `pre-commit` gate) in parallel with an eval cache via **`nix-fast-build`**, replacing the serial `nix flake check` build step. `nix-fast-build` is exposed as `packages.<system>.nix-fast-build` (a pinned-nixpkgs passthrough) so CI runs it reproducibly via `nix run .#nix-fast-build` without baking a CI-only tool into the dev-shell or the image
  - A new `docs/rfcs/ADR-flake-checks-tier0.md` records the tiering: pure, source-only checks are Tier 0 (nix-driven, cacheable, portable), while effectful jobs (image testinfra, integration, vulnix CVE-DB, multi-arch/publish, the impure pre-commit hooks and repo/git-dependent pytest units) stay GitHub-Actions-orchestrated. It also records the driver decision (nix-fast-build on existing runners now; garnix as a documented future option; Tier-1 self-hosting deferred)
  - The flake output schema `nix-fast-build` does not build (the treefmt `formatter`, the `checks` names, the `install` app, the nixos/homeManager modules) is now validated in CI by `tests/test_flake_checks.py`, preserving what the removed `nix flake check` covered
- **`checks.pre-commit` flake gate via git-hooks.nix + prek** ([#778](https://github.com/vig-os/devcontainer/issues/778))
  - Added the [`cachix/git-hooks.nix`](https://github.com/cachix/git-hooks.nix) input and a `checks.pre-commit` output that runs the **sandbox-pure subset** of the pre-commit hooks under `nix flake check`, driven by the `prek` runner (`package = pkgs.prek`) — no network, no project venv. It reuses the `treefmt` wrapper for the single formatting hook (nixfmt + ruff-format + taplo), the nix-provided pure linters (`ruff`, `shellcheck`, `yamllint`, `typos`, `taplo lint`, `just --fmt --check`), the `pre-commit-hooks` meta hooks, and the `vig-utils`/`bandit` hooks wired to hermetic Nix binaries — so the flake is a Nix-verified guarantee that the committed config's pure hooks stay correct
  - Impure/generator/stage-gated hooks (`generate-docs`, `sync-manifest`, `pip-licenses`, `pymarkdown`, `no-commit-to-branch`, `destroyed-symlinks`, `check-agent-identity`, and the `commit-msg`/`prepare-commit-msg` hooks) stay runner-only in the committed `.pre-commit-config.yaml`; the two-artifact model is documented in `docs/NIX.md`
- **Docs: local Nix image build/iterate loop + downstream `agent-models.toml` customization** ([#717](https://github.com/vig-os/devcontainer/issues/717))
  - `docs/NIX.md` gained a "Building and iterating the image locally" section: when to build locally vs. pull the published image, the `just build` → `just test-image` iterate loop, and that `just build` tags `<repo>:dev` (the tag the default `test`/`test-image`/`test-integration` recipes use and auto-build)
  - `docs/SKILL_PIPELINE.md` gained a "Customizing models downstream" note under **Model Selection** explaining how a consuming project overrides the `[models]` tiers and `[skill-tiers]` assignments in its own committed `.claude/agent-models.toml` — no recipe edits needed
- **Flake polish: treefmt-nix, deadnix/statix gates, NixOS/home-manager modules, `nix run .#install`** ([#777](https://github.com/vig-os/devcontainer/issues/777))
  - `nix fmt` now runs [`treefmt`](https://github.com/numtide/treefmt-nix) across every supported language in one pass (`nixfmt-rfc-style` for `*.nix`, `ruff format` for `*.py`, `taplo` for `*.toml`), wrapping the same formatters the pre-commit hooks already run so the editor, hooks, and CI agree on one formatting
  - Added `checks.deadnix` and `checks.statix` (dead-Nix-code + anti-pattern linters), scoped to the authored `flake.nix`; `deadnix` and `statix` also join `devTools`
  - Added `nixosModules.default` and `homeManagerModules.default` that install the shared `devTools` toolchain into a NixOS / home-manager configuration via `programs.vigos-devtools.enable = true`
  - Added `apps.install` so `nix run github:vig-os/devcontainer#install` bootstraps a consumer project straight from the flake (wrapping `install.sh`, which stays the behavior SSoT)
- **Secrets-management pattern ADR (sops-nix/age + OIDC)** ([#780](https://github.com/vig-os/devcontainer/issues/780))
  - Added `docs/security/ADR-secrets-management.md` recording the storage/delivery pattern for two secret classes — sops-nix + age for runtime/downstream-consumer secrets (each consumer decrypts with their own key, no per-repo GitHub-secret dance) and GitHub OIDC for cloud/registry auth — plus the honest caveat that on hosted runners SOPS relocates the root of trust to one bootstrap key rather than eliminating the GitHub secret, with OIDC as the only true no-stored-secret lever. Classifies each current stored secret (`CACHIX_AUTH_TOKEN`, `RELEASE_APP_*`, `COMMIT_APP_*`) as OIDC / sops / keep, notes GHCR-via-`GITHUB_TOKEN` and keyless cosign are already correct, and ships an inert reference example under `docs/security/examples/sops-nix/`. Complements the agent-behaviour standard in [#786](https://github.com/vig-os/devcontainer/issues/786) (design only; no workflow changed)
- **Nix dev-environment strategy ADR (activation / shell definition / local services)** ([#794](https://github.com/vig-os/devcontainer/issues/794))
  - Added `docs/rfcs/ADR-nix-devenv-strategy.md` recording why the org uses `pkgs.mkShell` (via `mkProjectShell`) + `nix-direnv` and rejects `devenv`/`numtide/devshell` as the shared builder. Reframes the recurring "direnv vs devenv vs devshell vs mkshell" question as three separable axes — activation (`nix-direnv` vs `nix develop`), shell definition (`mkShell` vs `devshell` vs `devenv`), and local services (`devenv up`-style orchestration) — noting devenv couples the latter two, which is the source of the confusion. Ratifies axes 1–2 on the dev-shell↔image parity-SSoT constraint plus devenv's ~165s IFD cold-eval (measured, [exo-pet/exo-fleet#76](https://github.com/exo-pet/exo-fleet/issues/76)), and adopts `process-compose` + `services-flake` for local services, with the shared `mkProjectServices` helper tracked in [#795](https://github.com/vig-os/devcontainer/issues/795). Authoritative for `vig-os`; a recommendation to `exo-pet`/`exoma` siblings. Cross-linked from `docs/NIX.md` (decision record; no code or workflow changed)
- **In-container `.#devShellTools` parity test** ([#754](https://github.com/vig-os/devcontainer/issues/754))
  - `tests/test_image.py` now reads the `devTools` toolchain SSoT straight from the flake (`nix eval --json .#devShellTools.<system>`, never a hardcoded list) and asserts every entry resolves on PATH inside the running image via `command -v`, parametrized per tool. Previously the SSoT was exercised only on the dev-shell side (`tests/test_flake_devshell.py`, skipped where the host lacks nix) while the image had a hand-curated check covering ~10 of the 27 tools — so adding a tool to `devTools` but not shipping it in the image went uncaught. This turns the SSoT into an actual image-side gate
- **Bake `/etc/nix/nix.conf` enabling `nix-command`/`flakes` and on-demand local builds** ([#739](https://github.com/vig-os/devcontainer/issues/739), [#749](https://github.com/vig-os/devcontainer/issues/749))
  - The Nix-built image bundles CppNix but shipped no `nix.conf`, leaving the modern CLI's `nix-command`/`flakes` features disabled by default so ad-hoc on-demand tooling (`nix shell nixpkgs#<x>`, `nix run`, `nix eval`) failed without an explicit `--extra-experimental-features` flag. The `buildLayeredImage` bootstrap layer now writes `/etc/nix/nix.conf` with `experimental-features = nix-command flakes` and an empty `build-users-group =` so the in-image root/single-user/daemonless nix (which has no `nixbld` group) can do on-demand local builds — not just cache substitutions, e.g. a `rust-overlay` toolchain — instead of aborting with "the group 'nixbld' … does not exist" (the explicit `substituters`/`trusted-public-keys` are covered under Security, [#773](https://github.com/vig-os/devcontainer/issues/773))
- **Consolidated `docs/NIX.md` Nix reference** ([#255](https://github.com/vig-os/devcontainer/issues/255))
  - Added a single onboarding/architecture doc for the flake: the `devTools` toolchain SSoT and the dev-shell ↔ image parity guard, the stable/unstable channel split + fast-mover overlay, the Nix-built (`buildLayeredImage`) reproducible multi-arch image, the CppNix-vs-Lix and `pre-commit`-vs-`prek` decisions, the `vig-os` Cachix `direnv allow` flow, how `nixpkgs` bumps flow (Renovate `nix` manager + `vulnix` before/after), and the #639 publish-cutover — cross-linking `CONTRIBUTE.md`, `docs/NIX2CONTAINER.md`, and `docs/CONTAINER_SECURITY.md`
- **In-container Nix runtime smoke test** ([#675](https://github.com/vig-os/devcontainer/issues/675))
  - The `Nix Image (discovery)` workflow now runs a self-contained, network-free smoke script (`scripts/nix_runtime_smoke.sh`) inside the built image to prove the baked Nix toolchain actually *functions* (not merely that it is present, which is all the portable testinfra suite checked): `nix --version`, `direnv version`, a real `nix eval` exercising the evaluator with `nix-command`/`flakes`, and a `direnv allow`/`exec` round-trip — gating the build/test job so a broken in-container `nix`/`direnv` fails CI
- **Nix flake quality gates** ([#674](https://github.com/vig-os/devcontainer/issues/674))
  - Added a `formatter` output (`nixfmt-rfc-style`) so `nix fmt` formats nix files idempotently, a `nixfmt --check` pre-commit hook (nixfmt sourced from the flake dev-shell), lightweight flake `checks` (format check, dev-shell build, `devShellTools` eval), and a `nix flake check --accept-flake-config` step in the CI project-checks job
- **Install/init delivery-mode picker (`--mode devcontainer|direnv|both`)** ([#641](https://github.com/vig-os/devcontainer/issues/641))
  - `install.sh` gained a `--mode devcontainer|direnv|both` flag (accepts both `--mode X` and `--mode=X`), validated up front and passed through to `init-workspace.sh`. Empty means "let init-workspace decide": the one-line install runs non-interactively and defaults to `both` (unchanged behaviour)
  - `init-workspace.sh` gained the same `--mode` flag plus an interactive prompt when the mode is unset and prompts are enabled (default selection `both`); under `--no-prompts`/`--smoke-test` with no `--mode` it defaults to `both`. After the rsync scaffold it prunes to the chosen mode: `devcontainer` removes the `flake.nix` + `.envrc` stub, `direnv` removes the `.devcontainer/` scaffold, and `both` keeps everything (prune is idempotent and scoped to the new workspace)
- **Downstream minimal flake stub (non-overwriting) + `nix2container` production builder** ([#640](https://github.com/vig-os/devcontainer/issues/640))
  - Scaffold `assets/workspace/flake.nix` (a minimal stub consuming the shared toolchain as a flake input — `vigos.url = github:vig-os/devcontainer`, `nixpkgs.follows = vigos/nixpkgs`, `vigos.lib.mkProjectShell` + a placeholder `extraPackages`) and `assets/workspace/.envrc` (`use flake` via nix-direnv). Updating the dev environment is `nix flake update vigos`; it never overwrites user files
  - Added both to the `PRESERVE_FILES` never-overwrite class in `init-workspace.sh` (same guarantee as `justfile.project`) and committed the template `.envrc` (un-ignored in the template `.gitignore`, with `.direnv/`/`.envrc.local` still ignored)
  - Documented the `nix2container` production-image pattern (`docs/NIX2CONTAINER.md`) with a buildable example (`examples/nix2container-production/`) that derives a minimal runtime image from the same pinned `nixpkgs`, plus a note on the future opt-in modular language shells
  - CI now gates the stub: a `nix flake check ./assets/workspace --override-input vigos path:.` step (and a `tests/test_downstream_flake.py` parity test) validates the scaffold against the working-tree toolchain, so an `lib.mkProjectShell`/`overlays.default` API change can't silently break a downstream `direnv allow`
- **`vulnix` + SBOM CVE scanning for the Nix image; re-authored security policy** ([#637](https://github.com/vig-os/devcontainer/issues/637))
  - Added a nightly `scan-nix-image` job that builds the image's package closure (new flake `packages.devcontainerImageEnv`) and runs `vulnix` (the nixpkgs-native CVE scanner) as the primary signal, since a Nix image has no apt/dpkg database for Trivy's OS scanner; Trivy stays on to emit a CycloneDX SBOM and an SBOM-mode vuln view (defence in depth), and both scanners' output is archived as `vulnix`-vs-Trivy overlap evidence
  - Added the `vulnix-gate` utility (`packages/vig-utils`) and the `.vulnixignore` exception register: a HIGH/CRITICAL finding (CVSS v3 ≥ 7.0) blocks only when it is not covered by a non-expired exception. `.vulnixignore` reuses the `.trivyignore` `Expiration:` format and the `check-expirations` validator (pre-commit + CI), and exposes a pinned `packages.vulnix` for reproducible scans. The gate is non-blocking during discovery and becomes the #639 go/no-go gate at cutover
  - Re-authored `docs/CONTAINER_SECURITY.md` for the Nix posture: dropped the `apt --only-upgrade` escape hatch and the "why not `apt-get upgrade`" section, made "advance the pinned `nixpkgs` rev" the primary CVE lever, and documented the dual `.vulnixignore`/`.trivyignore` registers and the residual Debian `:latest` scan until decommission (#642)
- **Multi-arch Nix image (amd64 + arm64) discovery build** ([#636](https://github.com/vig-os/devcontainer/issues/636))
  - The `Nix Image (discovery)` workflow now builds `packages.devcontainerImage` natively on an amd64 (`ubuntu-24.04`) + arm64 (`ubuntu-24.04-arm`) matrix — no QEMU or cross-compilation — pushes per-arch discovery tags (`nix-dev-amd64`, `nix-dev-arm64`), and assembles a top-level multi-arch index (`nix-dev`) with `docker buildx imagetools create`, verifying both platforms via `imagetools inspect`
  - `cachix-action` runs with an auth token on every leg so the arm64 closure is pushed to the `vig-os` Cachix cache; the workflow stays `continue-on-error` and only touches the disposable `nix-dev*` tags — the versioned/`:latest` publish-cutover remains #639
- **Renovate `nix` manager for `flake.lock` maintenance** ([#638](https://github.com/vig-os/devcontainer/issues/638))
  - Enabled the Renovate `nix` manager and weekly `lockFileMaintenance` in `renovate.json` so flake inputs (notably `nixpkgs`) are bumped through the normal PR/CI gate; the existing `pep621`, `npm`, `github-actions`, and `dockerfile` managers are retained
  - Documented the compensating control in `docs/CONTAINER_SECURITY.md`: every `flake.lock`/nixpkgs-bump PR must include a `vulnix` before/after diff, since the `nix` manager reports only the input revision change and not which CVE a bump fixes
- **De-duplicate the flake into the toolchain SSoT** ([#631](https://github.com/vig-os/devcontainer/issues/631))
  - Factored a single `devTools` list in `flake.nix` as the source of truth shared by the dev-shell now and the image later, absorbing the agent-CLI toolkit (`rg`, `fd`, `bat`, `eza`, `delta`, `lazygit`, `zoxide`, `starship`, `freeze`, `expect`, `nvim`) plus `claude` ([#545](https://github.com/vig-os/devcontainer/issues/545))
  - Pinned `nixpkgs` to `nixos-25.05` and added a `nixpkgs-unstable` input overlaid only for fast-movers (`uv`, `gh`, `claude-code`); refreshed `flake.lock`
  - Added reusable flake outputs `lib.mkProjectShell`, `overlays.default`, and a `packages.devcontainerImage` stub for the later image build
  - Added a non-blocking `Nix Cachix` workflow (with `workflow_dispatch`) that builds the dev-shell and pushes its closure to the `vig-os` Cachix cache
  - Added a per-tool `nix develop -c <tool> --version` parity test driven from the flake SSoT to guard against future dev-shell/image drift
- **nix-direnv onboarding fast path** ([#633](https://github.com/vig-os/devcontainer/issues/633))
  - Switched `.envrc` from bare `use flake` to nix-direnv: the dev-shell evaluation is now GC-rooted and cached under `.direnv/`, so re-entering the directory is instant and the closure is never garbage-collected; nix-direnv self-bootstraps on first `direnv allow` and falls back to bare `use flake` when unavailable
  - Documented the clone → `direnv allow` onboarding flow, the `vig-os` Cachix substituter (binary fetch instead of from-source build on first allow), and enabling the `nix-command`/`flakes` experimental features in `CONTRIBUTE.md` ([#255](https://github.com/vig-os/devcontainer/issues/255))
- **Build the devcontainer image with Nix (`buildLayeredImage`, non-publishing)** ([#634](https://github.com/vig-os/devcontainer/issues/634))
  - Fleshed out `packages.devcontainerImage` from a stub into a real, bit-reproducible image assembled by `dockerTools.buildLayeredImage` (not a Dockerfile `FROM`); a `--rebuild` verifies the closure hash is identical
  - Baked the in-container Nix evaluator (upstream CppNix, `pkgs.nix`) plus `direnv`/`nix-direnv` into the closure so `nix`/`direnv` are live inside the container; documented the CppNix-vs-Lix and `pre-commit`-vs-`prek` decisions in the flake
  - Reproduced the Debian bootstrap layers in Nix: locale via `glibcLocales` + `LOCALE_ARCHIVE` (no `locale-gen`), `/root/assets`, pre-commit cache dir, template `.venv` scaffold (`UV_PYTHON_DOWNLOADS=never`, `UV_PYTHON=<nix python3.14>`), the `precommit`/`cc`/`cld` aliases, and `IS_SANDBOX=1`
  - Added `fakeNss` (root uid-0 user database) and a sticky `/tmp` to close the first FHS gaps surfaced by the portable testinfra (fixing `ssh`, `whoami`, and `tmux`)
  - Added a non-publishing `Nix Image (discovery)` workflow (with `workflow_dispatch`) that builds the image and runs the portable testinfra under `continue-on-error: true`

### Changed

- **BREAKING for consumers — this release is the Nix publish-cutover** ([#639](https://github.com/vig-os/devcontainer/issues/639), [#625](https://github.com/vig-os/devcontainer/issues/625))
  - From this release on, the published image (`:latest` and every versioned tag) is the Nix-built image: pure-Nix userland with **no `apt`/`dpkg`**, a `docker → podman` shim (no Docker engine), and uv-managed CPython 3.14 (pin `requires-python` as a range, never an exact patch). See `docs/MIGRATION.md` for the full consumer contract
  - The final Debian-built release is **0.3.9**; it stays pullable indefinitely but frozen (no CVE fixes). Rollback/stay-behind: pin `DEVCONTAINER_VERSION=0.3.9` in the repo-root `.vig-os`
  - Heads-up: the next release cycle renames the project `devcontainer` → `devkit`, moving the image to a new GHCR package `ghcr.io/vig-os/devkit` ([#781](https://github.com/vig-os/devcontainer/issues/781))
- **Scaffolded devcontainer verbs renamed `up`/`down`/… → `devc-up`/`devc-down`/…** ([#795](https://github.com/vig-os/devcontainer/issues/795), completed by [#806](https://github.com/vig-os/devcontainer/issues/806))
  - The managed `.devcontainer/justfile.devc` namespaces its compose-stack verbs — `devc-up`, `devc-down`, `devc-status`, `devc-logs`, `devc-shell`, `devc-restart`, `devc-open` — so generic verb names stay free for project use (the new opt-in `services` recipe was the trigger: `up` was squatted by the devcontainer stack). The file is managed (replaced on upgrade), so consumers pick the rename up automatically on their next upgrade; muscle memory is the only breakage
  - The audit follow-up (#806) completes the namespacing: `check` → `devc-check` and `devcontainer-upgrade` → `devc-upgrade` (recipes, their hint strings, and the `version-check.sh` notification text), freeing the generic `check` name for project use
- **Git-hook runner migrated from `pre-commit` to `prek`** ([#778](https://github.com/vig-os/devcontainer/issues/778), closes [#40](https://github.com/vig-os/devcontainer/issues/40))
  - The Rust [`prek`](https://github.com/j178/prek) (a faster, drop-in `pre-commit` replacement) is now the hook runner and joins the shared `devTools` SSoT, so it ships in both the dev-shell and the image; the standalone Python `pre-commit` is dropped from both — one fewer manylinux/FHS consumer in the image closure
  - The `.githooks` shims, `scripts/init.sh` (`prek prepare-hooks`), `just precommit` (`prek run --all-files`), the worktree setup (`prek install`), and the downstream scaffold now invoke `prek`; the baked hook cache is renamed `PREK_HOME=/opt/prek-cache` and the `precommit` shell alias runs `prek run`. The committed `.pre-commit-config.yaml` (root + scaffold) is unchanged and prek runs it as-is
  - The CI lint gate (`.github/actions/test-project`) now runs the whole committed hook suite via `prek run --all-files` (was `uv run pre-commit run --all-files`), so `prek` — not the Python `pre-commit` — is what CI validates against the impure hooks too; `pre-commit==4.6.0` is removed from `pyproject.toml` + `uv.lock` (and the now-vestigial `pre-commit-` dev-shell PATH exclusion in `setup-env` is dropped), completing the "dropped from both" migration
  - Migration-completeness follow-ups: the committed `check-yaml` hook now passes `--allow-multiple-documents` in both the runner and `checks.pre-commit` so the Nix gate is no longer more lenient than the runner on multi-document YAML; the worktree `prek install` wires all three hook stages (`-t pre-commit -t commit-msg -t prepare-commit-msg`) so commit-msg / prepare-commit-msg hooks run in worktrees; and the downstream scaffold's remaining `pre-commit`/`PRE_COMMIT_HOME` references (CI `env`, `container-ci-quirks.md`, `init-precommit.sh`) are repointed at `prek`/`PREK_HOME`
- **Nix image bakes the build-time placeholder manifest so workspace init takes the fast path** ([#718](https://github.com/vig-os/devcontainer/issues/718))
  - The flake bootstrap layer now generates `/root/assets/.placeholder-manifest.txt` (the file `init-workspace.sh` reads next to itself) by `grep`-listing every workspace asset that carries a `{{SHORT_NAME}}`/`{{ORG_NAME}}`/`{{GITHUB_REPOSITORY}}` token, at its in-image runtime path and sorted for bit-reproducibility. Previously the Nix image shipped without the manifest, so `init-workspace.sh` always fell back to a slow runtime `find`+`grep` over the whole scaffold; the fast substitution path now fires. Output is unchanged (the fallback already produced correct results) — this is a startup-time optimization only
- **CI provisions every job from the Nix flake — the ad-hoc `setup-env` install path (and its hardcoded `uv` pin) is gone** ([#720](https://github.com/vig-os/devcontainer/issues/720))
  - The `setup-env` composite action is now flake-only: it always installs Nix + Cachix and enters the flake dev-shell, so CI and local `nix develop` run the exact same toolchain (uv, Python, just, taplo, BATS, linters). The `provision-via-flake` toggle and the ad-hoc install steps (`astral-sh/setup-uv`, `actions/setup-python`, `taiki-e/install-action` for just, the taplo curl, and `bats-action`) — with their now-removed `install-python`/`python-version`/`install-just`/`install-taplo`/`install-bats` inputs and the unused `uv-version` output — are deleted
  - Resolves the version drift #720 was filed for: the second, hardcoded `uv` pin (`0.11.23`) in `setup-env` is removed, so the provisioned `uv` version now flows from a single source — the flake's overlaid `pkgs.uv.version` in `flake.lock`. The lightweight security and release-orchestration jobs (which previously used the ad-hoc path) now pull the warm `vig-os` Cachix closure instead; `security-scan.yml`'s Nix-image job drops its duplicate direct Nix/Cachix setup in favour of the shared action. Host-integration tools (podman, Node.js, the devcontainer CLI) keep their dedicated steps
- **`nix fmt` and the flake format gate now run treefmt (superseding the nixfmt-only formatter)** ([#777](https://github.com/vig-os/devcontainer/issues/777))
  - The `formatter` output is the treefmt wrapper (was `nixfmt-rfc-style` directly, #674) and the flake `checks.format` gate is replaced by `checks.formatting` (a `treefmt --fail-on-change` check covering nix, python, and toml — superseding the former `nixfmt --check`-over-`*.nix` gate from #774)
- **Image-closure Cachix push is now first-class and blocking on the trusted paths** ([#776](https://github.com/vig-os/devcontainer/issues/776))
  - Published images are now guaranteed **cache-backed**: on the trusted paths (push to `dev` and releases) the built image closure is pushed to the `vig-os` Cachix cache as a **blocking** step (`nix path-info --recursive ./result | cachix push`), so consumers substitute the exact pinned closure instead of rebuilding it from source. Previously the image closure only reached the cache incidentally (a non-blocking, discovery-only side effect of `cachix-action`)
  - `.github/actions/build-image` gained an opt-in `push-image-closure` input (default `false`) that performs the blocking push, guarded on a non-empty auth token — so per-PR CI stays **pull-only** and fork PRs (which lack `CACHIX_AUTH_TOKEN`) never fail. The release `build-and-test` job opts in; the `Nix Image (discovery)` workflow pushes each per-arch image closure on `dev` as the same blocking step (distinct from the still-non-blocking GHCR discovery *tag* push)
  - The release CVE gate (`vulnix-gate`) now also pushes the `devcontainerImageEnv` scan-target closure, so the vulnix scan surface is cache-backed too. Documented the guarantee in `docs/NIX.md` and `docs/CONTAINER_SECURITY.md`
- **Flake cheap-fix batch: darwin-guarded image outputs, single nixpkgs-unstable eval, uv downloads URL derived from version, Renovate wheel-hash rule, nixfmt over all `*.nix`** ([#774](https://github.com/vig-os/devcontainer/issues/774))
  - The Linux-only `packages` (`devcontainerImage` plus its `devcontainerImageEnv`/`vulnix` scan targets) are now exposed only on `*-linux` systems, so `nix flake check --all-systems` no longer aborts during the darwin `dockerTools` evaluation; the dev-shell stays cross-platform
  - `nixpkgs-unstable` is imported once per system and threaded into the fast-mover overlay, instead of being re-imported inside the overlay fixpoint on each application
  - `UV_PYTHON_DOWNLOADS_JSON_URL` is derived from `pkgs.uv.version` rather than a literal version pin, so it can no longer drift from the overlaid (floating) `uv`
  - Added a Renovate custom regex manager that tracks the `pip-licenses` wheel version pinned in `flake.nix` (the sha256/URL hash path is refreshed by hand when the bump PR lands)
  - The flake `checks.format` gate now runs `nixfmt --check` over every `*.nix` in the repo (source filtered to `.nix` files), not just `flake.nix`
- **Resync security-gate docs to reflect the blocking vulnix gate** ([#758](https://github.com/vig-os/devcontainer/issues/758))
  - `docs/NIX.md`, `docs/CONTAINER_SECURITY.md`, and the `security-scan.yml` summary string still described the nightly `vulnix` CVE gate as non-blocking / in a discovery phase, with a stale `builder: debian|nix` selector reference; the gate is now **blocking** (#639) and the build pipeline is Nix-only post-Debian-decommission (#642), so the wording is corrected to match
- **Offline skip-guard for network-dependent image tests** ([#761](https://github.com/vig-os/devcontainer/issues/761))
  - The image tests that fetch over the network — `test_uv_venv_workflow` (`uv add`/`uv sync` from PyPI) and `test_npm_global_install_resolves_on_path` (`npm install -g tsx` from the npm registry) — now `pytest.skip(...)` when the host cannot reach the relevant registry instead of failing on an offline/air-gapped runner. A reusable `_host_can_reach(host, hostname)` probe (generalizing the existing `_pypi_reachable` PyPI check) backs the guards; online runs still execute the tests unchanged
- **Applied the still-relevant Renovate dependency updates** ([#625](https://github.com/vig-os/devcontainer/issues/625))
  - Folded the open Renovate PRs that still apply post-migration onto the epic: `actions/cache` → v6.1.0 (the v6 service, superseding the v5.x bumps), `actions/attest`/`actions/attest-build-provenance` → v4.1.1, `actions/setup-python` and `taiki-e/install-action` (just) digest refreshes, and `pandas` 3.0.3 → 3.0.4 in the workspace template. Stale ones were dropped: the `python:3.14-slim-bookworm` Docker digest (the `Containerfile` is gone) and the `ruff` pip pin (sourced from the flake now, #697); the `uv` 0.11.23 → 0.11.25 bump is deferred to the flake↔setup-env version sync (#720)
- **`SECURITY.md` describes the Nix image security posture** ([#642](https://github.com/vig-os/devcontainer/issues/642))
  - Replaced the stale Debian/`Containerfile` base-image pin, the "Trivy in CI/release" line, the 78 Debian LOW-CVE `.trivyignore` note, and the nine legacy BATS-npm GHSA exceptions (the framework now ships from the flake) with the current `vulnix` + CycloneDX SBOM scanning model and the `.vulnixignore`/`.trivyignore` dual register, mirroring `docs/CONTAINER_SECURITY.md`
- **README now describes the Nix-built image** ([#673](https://github.com/vig-os/devcontainer/issues/673))
  - Replaced the stale `python:3.12-slim-trixie` Debian base-image claim with the actual build: a Nix flake assembled via `dockerTools.buildLayeredImage` (no Debian/Docker base), with CPython 3.14 and the toolchain from a pinned `nixpkgs`, bit-reproducible
- **Make `just init` Nix-first** ([#671](https://github.com/vig-os/devcontainer/issues/671))
  - Rewrote `scripts/init.sh` from a multi-OS package installer into a Nix-first gate + bootstrapper: it requires Nix (and direnv, unless `--no-direnv`) and the dev-shell toolchain, then performs one-time, idempotent project bootstrap (`uv sync --frozen --all-extras`, git hooks path, commit-message template, `pre-commit install-hooks`) with advisory `podman info` / `gh auth status` checks. It no longer installs any tool — the toolchain is the flake's `devTools` — and short-circuits inside the built image (`IN_CONTAINER=true`)
  - Repointed `docs/generate.py` and the `CONTRIBUTE.md.j2` template: the per-OS "Requirements" table is now a "Prerequisites: Nix + direnv + a working host container runtime" section, with the toolchain sourced from `flake.nix`
- **Nix image passes the full testinfra suite (toolchain parity)** ([#666](https://github.com/vig-os/devcontainer/issues/666))
  - Packaged `vig-utils` (and `pip-licenses` from its PyPI wheel, as it is not in nixpkgs) as Nix python packages exposed through a `python314.withPackages` env, and added `ruff`, `bandit`, `cargo-binstall`, `just-lsp`, and `typstyle` from nixpkgs — the Nix image now carries the project Python toolchain hermetically, replacing the Debian image's build-time `uv pip install`
  - Relaxed `requires-python` from `==3.14.6` to `>=3.14,<3.15` across the root, `vig-utils`, and workspace-template pyprojects: `flake.lock` is the reproducibility anchor now, so the exact pin was redundant and unsatisfiable against nixpkgs (3.14.4)
  - Adapted `tests/test_image.py` to the Nix toolchain (version prefixes are nixpkgs-pinned, so fast-movers/mismatched tools are checked for presence/run only; the pre-commit cache dir is asserted present rather than pre-populated, since a hermetic build cannot fetch hook repos), taking the suite to 63/63 — and made the `nix-image.yml` `build-and-test` job gate on it (discovery phase closed)
- **Stage the Nix publish-cutover; advance the nixpkgs baseline to 26.05** ([#639](https://github.com/vig-os/devcontainer/issues/639))
  - Bumped the pinned channel `nixos-25.05` → `nixos-26.05` (the "advance the rev" CVE lever), cutting the vulnix HIGH/CRITICAL surface 83 → 27 and Trivy HIGH 244 → 14 on the image; triaged the residual 27 into `.vulnixignore` (4 CPE-mismatch false positives — VS Code/Jenkins, not the binaries; 23 recent CVEs accepted as low-risk in an interactive dev container with a 3-month re-review)
  - Made the nightly `vulnix-gate` **blocking** (the #639 go/no-go gate) now that it is legitimately green, and archived the `vulnix`-vs-Trivy scan overlap in `docs/security/nix-cutover-scan-overlap.md` (zero overlap — disjoint surfaces, no finding class lost in the Debian→Nix switch)
  - Staged the publish-cutover so the versioned/`:latest` publish stays paused pending a deliberate Nix release: the nightly `vulnix-gate` is the go/no-go signal. The build pipeline became Nix-only once the Debian path was decommissioned (#642), so no `builder` toggle remains — the interim `builder: debian|nix` selector this issue introduced was superseded by that decommission
- **Make `.claude/` the single source of truth for agent rules and skills** ([#626](https://github.com/vig-os/devcontainer/issues/626))
  - Moved the 30 agent skills from `.cursor/skills/` to `.claude/skills/` and rewrote the 29 `.claude/commands/*.md` wrappers to point at the new paths
  - Split the seven `.cursor/rules/*.mdc`: static principles (coding principles, commit messages, changelog, single source of truth) are now consolidated in `CLAUDE.md`; workflow rules (`branch-naming`, `tdd`, `subagent-delegation`) became on-demand `.claude/skills/`
  - Ported `agent-models.toml` and `worktrees.json` to `.claude/`, updated the docs generator, pre-commit hooks, shell entrypoints, and the workspace sync manifest, and deleted the root `.cursor/` directory
- **Drive autonomous worktree pipelines with the `claude` CLI** ([#627](https://github.com/vig-os/devcontainer/issues/627))
  - `just worktree-start`/`worktree-attach` now launch `claude --dangerously-skip-permissions` in the tmux session instead of `cursor-agent` (`agent chat --yolo --approve-mcps`); the cursor-specific directory-trust step and the `tmux send-keys "a"` approval trigger are no longer needed and have been removed
  - Prerequisite, authentication (`claude auth status`/`claude auth login`, `ANTHROPIC_API_KEY`), and `scripts/requirements.yaml` now reference the `claude` CLI rather than the Cursor Agent CLI
- **Migrate the workspace template and editor glue off Cursor (VS Code only)** ([#629](https://github.com/vig-os/devcontainer/issues/629))
  - New workspaces now scaffold `.claude/` (skills, `agent-models.toml`, `worktrees.json`) instead of the removed `.cursor/` template tree; the sync manifest carries the `.claude/` payload accordingly
  - `just open` launches VS Code only (dropped the `command -v cursor` fallback), and `verify-auth.sh` no longer scans the `cursor-remote-ssh` SSH-agent socket
  - `COMMIT_MESSAGE_STANDARD.md` now refers to VS Code rather than "VS Code / Cursor"
- **Make the image testinfra suite portable across Debian and Nix images** ([#635](https://github.com/vig-os/devcontainer/issues/635))
  - Replace dpkg `host.package(...).is_installed` checks (git, curl, openssh-client, nano, tmux, rsync) with path-agnostic `--version`/`-V` runs
  - Resolve `gh`, `just`, `hadolint`, `taplo` and cargo-installed tools via PATH (`command -v`) instead of hardcoded `/usr/local/bin` / `/root/.cargo/bin` / `/root/.local/bin` locations
  - Drop the `DEBIAN_FRONTEND` environment assertion and the apt-sourced version-prefix checks (git, curl, tmux, rsync) from `EXPECTED_VERSIONS`
- **Provision CI build/test tooling from the flake dev-shell** ([#632](https://github.com/vig-os/devcontainer/issues/632))
  - The `setup-env` action gained a `provision-via-flake` mode that installs Nix (SHA-pinned `install-nix-action`) and the `vig-os` Cachix substituter, builds the flake dev-shell, and prepends its tools to `PATH`, replacing the ad-hoc installs of `uv`/Python, `just`, `hadolint`, and `taplo`
  - Enabled the mode in the CI build/test path (`build-image`, `test-image`, `test-integration`, `project-checks`) so jobs run inside the flake shell (the toolchain SSoT); `podman`, Node.js, BATS, and the devcontainer CLI keep their dedicated install paths
  - Set `UV_PYTHON_DOWNLOADS_JSON_URL` in the flake dev-shell so the nixpkgs `uv` (whose embedded Python-download list is stripped) can fetch the project's pinned CPython `3.14.6`, which nixpkgs does not package, letting `uv sync --frozen` succeed under flake provisioning
  - Keep `podman` off the flake-provisioned `PATH` so the runner's rootless-configured host `podman` is used (the nix-store `podman` cannot reach the host's setuid `newuidmap`/`newgidmap`, so `podman info` failed)

### Removed

- **Removed the sidecar / multi-container capability** ([#799](https://github.com/vig-os/devcontainer/issues/799))
  - Dropped the `just sidecar`/`just sidecars` recipes, the `docker-compose.project.yaml` sidecar examples, the sidecar test fixtures (`sidecar.Containerfile`, `test-build.sh`, the fixtures `justfile`, the `test-sidecar` compose service) and `TestSidecarConnectivity`, and `hadolint` from `devTools` (unused since the Containerfile lint hook was dropped in #642; the deleted sidecar Containerfile was its last Dockerfile-like artifact)
  - Migration: use Nix devShells for toolchains and `process-compose`/`services-flake` ([#795](https://github.com/vig-os/devcontainer/issues/795)) for local services; the Docker-out-of-Docker socket for building containers is retained
- **Retire `scripts/requirements.yaml`** ([#671](https://github.com/vig-os/devcontainer/issues/671))
  - Deleted the per-OS dependency manifest and its consumers (the `load_requirements`/`format_requirements_table`/`format_install_commands` helpers in `docs/generate.py` and their tests). `flake.nix` `devTools` is now the single source of truth for the toolchain, ending the dual-SSoT drift
- **Decommission the Debian build path** ([#642](https://github.com/vig-os/devcontainer/issues/642))
  - Deleted the root `Containerfile`, `scripts/prepare-build.sh`, `scripts/build.sh`, and the `.hadolint.yaml` config (plus its synced workspace copy); the image now builds Nix-only
  - Removed the `hadolint` pre-commit hook and its `setup-env`/`test-project` install wiring, the `hadolint` and Containerfile entries from `scripts/requirements.yaml` and `scripts/manifest.toml`, and the `Containerfile`/build-script `CODEOWNERS` entries
  - `build-image`, `release.yml`, and `ci.yml` are now Nix-only
  - Dropped the Debian `scan-latest` nightly Trivy job, the ~78 Debian OS-package CVE entries from `.trivyignore`, and the Renovate `dockerfile` manager; `docs/CONTAINER_SECURITY.md` now reads as Nix-only
- **Remove the `cursor-agent` CLI install from the image** ([#628](https://github.com/vig-os/devcontainer/issues/628))
  - Dropped the unpinned `curl … cursor.com/install` build step and its `/root/.local/bin` PATH entry, leaving an all-nixpkgs toolchain ahead of the Nix migration
  - Removed the coupled `test_cursor_agent_installed` image test

### Fixed

- **vulnix CVE scans survive `nvd.nist.gov` outages via a self-hosted NVD feed mirror** ([#870](https://github.com/vig-os/devcontainer/issues/870))
  - `nvd.nist.gov` is chronically throttled/unstable (upstream `nix-community/vulnix#171`): cold scan runs crawled the full NVD year-feed set for tens of minutes and failed with `ReadTimeoutError`/`IncompleteRead`, blocking both the nightly gate and the release publish gate. A dedicated public mirror, [`vig-os/nvd-mirror`](https://github.com/vig-os/nvd-mirror), now downloads the NVD 2.0 feed files (`nvdcve-2.0-<6 years>.json.gz` + `modified`) with resumable retry, validates them, and serves them on GitHub Pages — the only job that talks to NVD
  - `security-scan.yml` and the `release.yml` `vulnix-gate` now run `vulnix --mirror https://vig-os.github.io/nvd-mirror/`, fetching NVD data from a CDN-backed mirror instead of `nvd.nist.gov`, so an NVD outage can no longer fail a scan or block a release. The mirror also localizes the NVD-format dependency to one place should the feeds ever change
- **Renovate changelog automation no longer self-triggers an empty-commit loop and keeps the workspace mirror in sync** ([#863](https://github.com/vig-os/devcontainer/issues/863))
  - The changelog commit is pushed with a GitHub App token (which re-triggers workflows), but the build gated only on the PR author (permanently `renovate[bot]`) and never the pusher, and `commit-action` has no empty-diff guard — so the bot's own no-op commits fired fresh `synchronize` events without end (#862 accrued 150+ identical empty commits before the build was disabled by hand). The build now skips `synchronize` events raised by the changelog commit bot (`github.event.sender.login`), severing the loop
  - The automation committed only root `CHANGELOG.md`, leaving the `scripts/manifest.toml` mirror `assets/workspace/.devcontainer/CHANGELOG.md` stale so the `sync-manifest` gate failed on every Renovate PR; the build now mirrors the verbatim copy and commits both files
- **rc4 field-validation fix batch: direnv-mode commits, pipe-safe scripts, prune/typos/installer hardening** ([#859](https://github.com/vig-os/devcontainer/issues/859))
  - Scaffolded `.githooks/*` now use `#!/usr/bin/env bash` (hosts without `/bin/bash`, e.g. NixOS, could not run them) and accept the nix dev-shell (`IN_NIX_SHELL`) as a sanctioned commit environment — previously direnv-mode consumers could not commit at all (the guard demanded the container)
  - Restored the `${BASH_SOURCE[0]:-$0}` pipe-safety fallback in the scaffolded lifecycle scripts (`initialize`/`post-create`/`post-attach`/`version-check`) — a regression from the 0.3.x scaffold caught by a consumer's own regression tests
  - `--mode devcontainer` no longer deletes a consumer's **pre-existing** `flake.nix`/`.envrc` (two real repos lost their own nix-direnv setup); the prune now only removes stub files the scaffold itself created, mirroring the #738 guard
  - The installer's final `just sync` is non-fatal when the preserved old-generation `justfile.project` predates the `sync` recipe (warns and points to MIGRATION.md instead of failing an otherwise complete scaffold)
  - The typos hook (repo + scaffold) passes `--force-exclude` so `[files] extend-exclude` applies to explicitly-passed staged files — three consumer repos hit garbage findings on committed binary artifacts (PDFs, SVGs, `.bin` fixtures)
  - `docs/MIGRATION.md` gained the field-validated "Upgrading an existing 0.3.x consumer" checklist (prek recipe migration, recipe renames, typos config precedence/shadowing, artifact excludes, name re-derivation)
- **Shipped consumer `prepare-release.yml` caps its PR body under GitHub's 65,536-char limit** ([#857](https://github.com/vig-os/devcontainer/issues/857))
  - #812 capped the PR body only in this repo's own workflow; the scaffolded consumer copy still interpolated the full frozen changelog section uncapped, so a consumer with a large release (the 0.4.0-rc3 smoke test seeds this repo's ~67k-char section) failed `Create draft PR to main` with `GraphQL: Body is too long`. The shipped workflow now applies the same line-boundary truncation with a pointer to the release branch's full `CHANGELOG.md`
- **Scaffold ships `.typos.toml` so the shipped typos hook passes out of the box** ([#855](https://github.com/vig-os/devcontainer/issues/855))
  - The scaffolded `.pre-commit-config.yaml` runs the `typos` hook, but the exception config stayed repo-local — consumers linted scaffold-shipped content (`version-check.sh`'s `Nd` duration syntax, the synced changelog's "unexcepted" CVE-policy term) with zero exceptions and failed immediately, as the 0.4.0-rc2 smoke test showed. `.typos.toml` now syncs into the workspace template via `scripts/manifest.toml`, same as `.yamllint`/`.pymarkdown`
- **`install.sh --version` now pins the scaffolded `.vig-os` to the requested version** ([#852](https://github.com/vig-os/devcontainer/issues/852))
  - The Nix image bakes the release it was built from into the scaffolded `.vig-os` (correct for finals, where the repo pin is bumped at finalize — but stale for release candidates), and `install.sh` never wrote its `--version` into the scaffold. An RC install therefore pinned the previous release: the 0.4.0-rc1 smoke test scaffolded the new prek-era workspace pinned to the Debian 0.3.9 image and its CI lint failed with `prek: command not found`. `install.sh` now forwards an explicit `--version` as `VIG_OS_VERSION` and `init-workspace.sh` pins it in `.vig-os` post-scaffold; plain `latest` installs keep the baked pin
- **Release-lane Trivy scan aligned with the ratified awareness-only posture** ([#849](https://github.com/vig-os/devcontainer/issues/849))
  - `release.yml`'s build-and-test Trivy step was the last Debian-era blocking scanner (`exit-code: 1` with only `.trivyignore`), failing the candidate on embedded language-ecosystem HIGHs already triaged into `.vulnixignore`. Per the #637 decision the Nix image's blocking CVE control is the vulnix-gate; the step is now non-blocking (`exit-code: 0`, `continue-on-error`) with its table kept in the log as awareness signal, mirroring `security-scan.yml` and `ci.yml`
- **`setup-env` no longer flakes on a SIGPIPE race when listing the provisioned dev-shell PATH** ([#847](https://github.com/vig-os/devcontainer/issues/847))
  - The provisioning step's `grep '^/nix/store' | head -50` summary runs under the runner's `pipefail` shell; once the dev-shell PATH topped 50 nix-store entries, `head` exiting early could SIGPIPE `grep` (exit 2) and fail the step — a scheduling race that killed a release build-and-test leg. `sed -n '1,50p'` consumes the whole stream and prints the same summary
- **Release lane fixed for the Nix stack: current runners + tolerated vulnix findings exit** ([#842](https://github.com/vig-os/devcontainer/issues/842))
  - `release.yml`'s build-and-test matrix still pinned Debian-era `ubuntu-22.04`/`ubuntu-22.04-arm` runners, whose podman 3.4.4 breaks rootless volume UID mapping — `init-workspace.sh`'s in-container rsync failed to chmod the `/workspace` scaffold (`Operation not permitted`), killing the integration tests that pass everywhere else on `ubuntu-24.04` (podman 4.9.3). The matrix now uses the same `ubuntu-24.04`/`ubuntu-24.04-arm` expression as `nix-image.yml`
  - The release `Run vulnix` step missed `security-scan.yml`'s `|| rc=$?` capture, so under the runner's `bash -e` a normal exit 2 (findings present, to be judged against `.vulnixignore`) aborted the step before the vulnix-gate ran. The step now uses the nightly's capture/retry pattern (crashes with exit > 2 or invalid JSON still fail loudly)
- **Release pipeline no longer fails when the release changelog exceeds GitHub's PR-body limit** ([#810](https://github.com/vig-os/devcontainer/issues/810))
  - The `Create draft PR to main` step passed the entire frozen changelog section as the PR body; GitHub caps PR bodies at 65,536 characters, so a large release (e.g. 0.4.0 at ~64k chars) overflowed with `GraphQL: Body is too long` and the release rolled back. The step now caps the body, truncating the changelog at a line boundary and pointing to the full `CHANGELOG.md` on the release branch when it would overflow; small releases still inline the whole changelog unchanged
  - The same uncapped rebuild existed in `release.yml`: the finalize-path `Refresh release PR body from finalized changelog` step (which would have crashed the final release run mid-finalize and triggered rollback) and the rollback-path `Restore release PR body` step. Both now apply the same cap
- **Scaffold justfile audit: worktree recipes reachable, compose docs de-stale'd** ([#806](https://github.com/vig-os/devcontainer/issues/806))
  - The scaffold root `justfile` now imports `.devcontainer/justfile.worktree` (`import?`, so direnv-mode workspaces still parse): the shipped `.claude` worktree skills invoke `just worktree-start`, but nothing imported the recipes, so they were unreachable in consumer repos
  - The shipped `.devcontainer/README.md` no longer documents the long-removed `docker-compose.override.yml(.example)` workflow; it now describes the real layering (`docker-compose.project.yaml` team-shared / `docker-compose.local.yaml` personal) that #799 deliberately kept
  - Dropped a vacuous image-test assertion on a `docker-compose.local.yml` (`.yml`) spelling nothing ships, and aligned the dev-env ADR's illustrative services verb with the shipped `just services` recipe. The audit found no other compose-era leftovers: the repo-root justfiles are clean and the project/local compose layering is intentional
- **Review-nit batch: dry-run/scaffold-guard, summary cancel handling, help/message fixes** ([#759](https://github.com/vig-os/devcontainer/issues/759))
  - `install.sh` `--dry-run` now derives the shown command from the real `CMD` array via `printf '%q'` (no hand-maintained duplicate string), and the automatic "initial project scaffold" commit is guarded so it only runs for a freshly scaffolded (empty) target instead of sweeping a pre-populated directory
  - `release.yml` now treats a `cancelled` required job as not-green (it triggers rollback like a failure), so a cancellation can no longer leave a partial release un-rolled-back
  - `version-check.sh` help text corrected (`And (days)` → `Nd (days)`), and `init.sh` now reports "Pre-commit hook environments installed" (the `install-hooks` step only fetches hook environments)
- **Restore arm64 image-testing coverage post-merge** ([#760](https://github.com/vig-os/devcontainer/issues/760))
  - `nix-image.yml` (the only lane that builds + runs the portable testinfra suite natively on arm64) was push-filtered to the migration epic branch only, so once it merges the arm64 image would no longer be exercised on the integration branch — PR CI (`ci.yml`) builds and tests amd64 only. Added `dev` to the workflow's `push:` branch filter (keeping the existing `flake.nix`/`flake.lock`/workflow `paths:` guard) so the native amd64 + arm64 build/test matrix keeps running on `dev` post-merge
- **release.yml publish retags the loaded Nix image tag** ([#752](https://github.com/vig-os/devcontainer/issues/752))
- **install.sh `--skip-pull` works under docker; ci.yml runs safety via `uv run`** ([#757](https://github.com/vig-os/devcontainer/issues/757))
  - `install.sh` checked for a present local image with the podman-only `$RUNTIME image exists`, which docker lacks, so `--skip-pull` always failed under docker; it now uses `$RUNTIME image inspect`, which works on both runtimes
  - The CI `safety` dependency scan was invoked bare instead of via `uv run`, so it ran outside the uv env (unlike the adjacent `uv run bandit`); it now runs via `uv run safety`
- **Dev-shell exposes `python3` + `pre-commit` (image parity), CI-safely** ([#729](https://github.com/vig-os/devcontainer/issues/729))
  - `mkProjectShell` now ships a bare `python3`/`pre-commit` on PATH so the downstream flake-input/direnv dev-shell matches the image. `setup-env` filters the Nix `python3-<ver>` (and `pre-commit`) out of the forwarded CI runner PATH so `uv` keeps building the project venv from the downloaded managed CPython. No new `LD_LIBRARY_PATH`, so the #703 FHS leak-guard is intact. A `nix develop --ignore-environment` parity test (and the FHS leak-guard) now run in the Project Checks job
- **Nix image runs pre-compiled PyPI (manylinux) wheels at runtime (arch-aware FHS loader + baked `LD_LIBRARY_PATH`)** ([#736](https://github.com/vig-os/devcontainer/issues/736))
  - The bare `dockerTools.buildLayeredImage` shipped neither the FHS dynamic loader (the `PT_INTERP` every manylinux wheel hardcodes) nor the Nix C++/compression runtime on the loader path, so runtime-installed PyPI binaries broke: standalone tools (consumer pre-commit configs pinning PyPI `ruff`/`typos`) aborted with `cannot execute: required file not found`, and C extensions dlopened by the baked CPython (`numpy`/`scipy`, pre-commit `pymarkdown`'s `pyjson5`) failed with `ImportError: libstdc++.so.6`
  - The image now ships an architecture-aware FHS loader (`/lib64/ld-linux-x86-64.so.2` on x86_64, `/lib/ld-linux-aarch64.so.1` on aarch64 — the loader name and FHS dir are derived from the build platform, so the arm64 build passes `test_fhs_loader_exists`) symlinked to the Nix glibc loader (newer glibc runs the old-glibc wheels via backward compatibility), and bakes `LD_LIBRARY_PATH` with `${stdenv.cc.cc.lib}/lib` (libstdc++/libgcc_s) + `${zlib}/lib` (libz) so both standalone wheel executables and C-extension `.so` files dlopened by the store CPython resolve their runtime libs. This is the image-scope analogue of the dev-shell [#698](https://github.com/vig-os/devcontainer/issues/698) fix, but ungated: an all-Nix container has no foreign FHS host binaries to pollute, so the `/etc/NIXOS` ABI gate never applies
- **Nix image bakes the template `/root/assets/workspace/.venv` (renameable prompt)** ([#735](https://github.com/vig-os/devcontainer/issues/735))
  - The image advertised `UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV` at `/root/assets/workspace/.venv` but never created it (the Debian image did). The published 0.3.x consumer `post-create.sh` runs `sed -i .../.venv/bin/activate` as its first venv step and aborted under `set -euo pipefail` (`exit 2`) when the file was missing — so git setup, gh auth, pre-commit install, and `just sync` never ran. The flake bootstrap layer now pre-creates the venv from the baked CPython (matching the advertised env vars, hermetic and network-free with no packages — `just sync` populates it), and normalizes the activate `VIRTUAL_ENV_PROMPT` to the quoted `"template-project"` form the consumer `post-create.sh` rename targets (so the prompt rename no longer no-ops)
- **`docker` now resolves in the Nix-built image (podman compatibility shim)** ([#740](https://github.com/vig-os/devcontainer/issues/740))
  - The image shipped `podman` but no `docker` binary, while the consumer `.devcontainer/docker-compose.yml` mounts the socket at `/var/run/docker.sock` and sets `DOCKER_HOST`/`CONTAINER_HOST`. Docker-out-of-Docker worked because podman honors `DOCKER_HOST`, but any recipe/script invoking `docker` literally failed with `command not found`. The bootstrap layer now bakes a tiny `docker -> podman` wrapper at `/usr/local/bin/docker` (already on the baked `PATH`) that execs the baked podman, so `docker`-literal callers get a working binary without pulling in the Docker engine
- **`install.sh --mode direnv --force` no longer clobbers a populated consumer repo** ([#738](https://github.com/vig-os/devcontainer/issues/738))
  - Re-initializing an existing project in `direnv` mode deployed the full workspace template over it: the scaffold `rsync` overwrote a real `pyproject.toml` with the generic template one, and copied the template `.devcontainer/` before the mode prune deleted the directory wholesale — destroying tracked files (`devcontainer.json`, project compose files, …). `pyproject.toml` is now in the never-overwrite `PRESERVE_FILES` class, and `direnv` mode excludes `.devcontainer/` from the copy and skips the prune when a populated `.devcontainer/` predates the (re)scaffold, so real project files survive untouched. `--force` still deploys the Nix/direnv stub (`flake.nix`, `.envrc`, `.vig-os`) onto repos that lack it
  - `install.sh` no longer prints a misleading `User configuration script not found … copy-host-user-conf.sh` warning in `direnv` mode, which scaffolds no `.devcontainer/` and therefore has no host-user-conf step to run
- **`/usr/bin/env` now exists in the Nix-built image** ([#727](https://github.com/vig-os/devcontainer/issues/727))
  - The bare `dockerTools.buildLayeredImage` had no `/usr/bin` at all, so the ubiquitous `#!/usr/bin/env <interp>` shebang failed with `/usr/bin/env: bad interpreter: No such file or directory` — breaking essentially every Node/Python/Ruby CLI (e.g. `node_modules/.bin/tsc`) for image-mode consumers. Added `dockerTools.usrBinEnv` (the FHS shim symlinking `/usr/bin/env` to coreutils `env`) to the image package set, alongside the existing `fakeNss` shim
- **`npm install -g` now lands CLIs on PATH in the Nix image** ([#728](https://github.com/vig-os/devcontainer/issues/728))
  - npm's default global prefix was the read-only `nodejs` nix-store path, whose `bin/` is not on `PATH` — so `npm install -g <tool>` reported success but the binary was unresolvable (`command -v <tool>` failed). The image now bakes `NPM_CONFIG_PREFIX=/usr/local` (already on the baked `PATH`) and creates a writable `/usr/local/bin` in the bootstrap layer, so globally installed CLIs resolve on `PATH`
- **`init-workspace --mode direnv` now produces a loadable `justfile`** ([#641](https://github.com/vig-os/devcontainer/issues/641))
  - The scaffolded root `justfile` hard-imported `.devcontainer/justfile.devc` and `.devcontainer/justfile.gh`, but `direnv` mode prunes `.devcontainer/` — so every `just` command (including init-workspace's own final `just sync`) failed to parse in a direnv-mode workspace. Made the two `.devcontainer/` imports optional (`import?`, matching `justfile.project`/`justfile.local`); the `sync` recipe lives in the preserved `justfile.project`, so `just sync` still works in all modes
- **Worktree recipes read agent config from the `.claude/` SSoT** ([#627](https://github.com/vig-os/devcontainer/issues/627))
  - The Cursor→Claude migration swapped the launch command but left `justfile.worktree` reading the removed `.cursor/` tree: a dead `_read_model` helper pointed at `.cursor/agent-models.toml`, and the branch-naming rule passed to `derive-branch-summary` was `.cursor/rules/branch-naming.mdc`. Removed the unused helper and repointed the rule at `.claude/skills/branch-naming/SKILL.md`; trimmed the stale `.cursor/` wording from the sync-manifest comment. Added `worktree-claude-cli.bats` / `test_claude_ssot.py` guards against entrypoints reading removed `.cursor/` config paths
  - `derive-branch-summary` (invoked by `just worktree-start` to name an unlinked branch) still shelled out to the removed `cursor-agent` binary (`agent --print --yolo --trust`); with no test exercising the non-`BRANCH_SUMMARY_CMD` path it slipped through CI. It now drives `claude --print --dangerously-skip-permissions`, and `agent-models.toml` tiers map to claude model aliases (`haiku`/`sonnet`/`opus`) instead of Cursor names (`composer-1.5`/`sonnet-4.5`/`opus-4.6`) so `--model` resolves
- **Integration tests now exercise the freshly-built image, not the published `DEVCONTAINER_VERSION`** ([#701](https://github.com/vig-os/devcontainer/issues/701))
  - The integration suite scaffolded a workspace from the image under test (`TEST_CONTAINER_TAG`) but then brought the devcontainer up from whatever `DEVCONTAINER_VERSION` resolved to (the published `0.3.9`), so it validated fresh scaffolding running inside a stale image. The `devcontainer_up`/`devcontainer_with_sidecar` fixtures now export `DEVCONTAINER_VERSION=TEST_CONTAINER_TAG`; compose reads the shell environment over `.env`, so the scaffolded `docker-compose.yml` resolves to the build under test (and every `devcontainer exec`, which inherits the environment, agrees). Added `test_devcontainer_runs_image_under_test` asserting the running container's image
- **Dev-shell resolves `pymarkdown`'s `pyjson5` `libstdc++` on NixOS without breaking `just` on FHS hosts** ([#698](https://github.com/vig-os/devcontainer/issues/698), [#703](https://github.com/vig-os/devcontainer/issues/703))
  - The `pymarkdown` hook runs from pre-commit's own manylinux-wheel Python env, whose dependency `pyjson5` is a C extension linked against `libstdc++.so.6`; on a NixOS host that library is off the loader path outside an FHS environment, so the hook aborted with `ImportError: libstdc++.so.6` and forced `--no-verify`. Unlike the standalone binaries in [#697](https://github.com/vig-os/devcontainer/issues/697), `pymarkdown` is not in nixpkgs, so the "add to `devTools` + `language: system`" recipe does not apply
  - `mkProjectShell` now appends the Nix C++ runtime (`${stdenv.cc.cc.lib}/lib`, libstdc++) to `LD_LIBRARY_PATH` **only on NixOS** (`[ -e /etc/NIXOS ]`), where it is both required (libstdc++ is off the default loader path) and ABI-safe (the system glibc *is* the Nix glibc). On an FHS host the system loader resolves `libstdc++` and nothing is exported — avoiding the `GLIBC_ABI_DT_X86_64_PLT not found` breakage an unconditional export caused in host `just`/bash recipes (whose `#!/usr/bin/env bash`, plus anything `/etc/ld.so.preload` forces `libstdc++` into, were dragged onto the Nix C++ runtime built against a newer glibc). The dev-shell parity tests are gated to NixOS and an FHS leak-guard (`test_devshell_no_nix_cxx_runtime_leak_on_fhs_host`) was added
- **pre-commit ruff/ruff-format/typos hooks now run on NixOS hosts (sourced from the flake)** ([#697](https://github.com/vig-os/devcontainer/issues/697))
  - The `ruff`, `ruff-format`, and `typos` hooks pulled compiled tools as generic-linux (manylinux) wheels from `astral-sh/ruff-pre-commit` and `crate-ci/typos`; a NixOS host cannot execute those binaries out of the box (no FHS `ld-linux`), forcing `--no-verify` on every local commit
  - Added `ruff` and `typos` to the flake `devTools` SSoT and converted the three hooks to `repo: local` / `language: system` (`ruff check --fix`, `ruff format`, `typos`), so they resolve their tool from the Nix dev-shell like the other local hooks — no host setup needed inside the dev-shell. Hook versions now track `nixpkgs`/`flake.lock` (Renovate `nix` manager) instead of upstream `rev:` pins, consistent with the #625 toolchain consolidation. The scaffolded `assets/workspace/.pre-commit-config.yaml` is `language: system` as well (no upstream-hook decoupling — downstream workspaces resolve the tools from the toolchain baked into the image)
  - Removed `ruff` from the project's uv dependency groups (`pyproject.toml`/`uv.lock`) and repointed `just lint`/`just format` to the flake `ruff` (dropping `uv run`). Otherwise the venv's `ruff` (a manylinux wheel) shadowed the flake `ruff` under `uv run` — which is how the `.githooks/pre-commit` hook and the `just` recipes invoke it — so `ruff` stayed broken on NixOS; the flake is now the single `ruff` source (its `[tool.ruff]` config is unchanged)
  - Declared `PATH` in the devcontainer image's OCI `config.Env`. `buildLayeredImage` symlinks the toolchain into `/bin` but set no PATH; `podman run` injects a default (so it worked), but `docker-compose` / `devcontainer exec` inherit `config.Env` verbatim, leaving the baked toolchain off PATH so `language: system` hooks could not resolve. Added an image test asserting the OCI config declares a PATH containing `/bin`
- **BATS suite no longer fails locally on the Nix toolchain (helper libraries unresolved)** ([#695](https://github.com/vig-os/devcontainer/issues/695))
  - `tests/bats/test_helper.bash` resolved the BATS helper libraries (`bats-support`/`-assert`/`-file`) from `node_modules` (npm) or the now-removed Debian `/usr/lib` path; on the Nix toolchain neither exists locally, so every `.bats` file errored in `setup()` (`Could not find library 'bats-support'`) and all 246 tests failed
  - Added `bats` wrapped with its helper libraries to the flake `devTools` SSoT and exported `BATS_LIB_PATH` in the dev-shell and image, so `bats_load_library` resolves the helpers from the Nix store; simplified `test_helper.bash` to that single path, switched `just test-bats` to the flake-provided `bats`, and removed the now-unused `bats*` npm dependencies. CI provisions BATS from the flake under `provision-via-flake` (the ad-hoc `bats-action` steps now run only for non-flake callers)
- **Host-executed scripts no longer fail on NixOS (non-portable `#!/bin/bash` shebang)** ([#687](https://github.com/vig-os/devcontainer/issues/687))
  - `install.sh`, `assets/workspace/.devcontainer/scripts/initialize.sh`, and `assets/workspace/.devcontainer/scripts/version-check.sh` hardcoded `#!/bin/bash`, which has no `/bin/bash` on NixOS and similar hosts, so they failed to execute (and `just test` aborted). Switched all three to the portable `#!/usr/bin/env bash` (already used by `scripts/init.sh`), which resolves `bash` via `PATH`
- **`allowed-signers` integration test no longer rejects valid ECDSA / security-key SSH keys** ([#688](https://github.com/vig-os/devcontainer/issues/688))
  - `test_allowed_signers_file_exists` only accepted `ssh-ed25519`/`ssh-rsa`, so a valid ECDSA (or FIDO `sk-*`) signing key spuriously failed; the assertion now accepts the full OpenSSH signing key-type set (mirroring the canonical list already used in `test_git_signing_key_configured`), including the `ecdsa-sha2-nistp*` curves and the `sk-ssh-ed25519@openssh.com` / `sk-ecdsa-sha2-nistp256@openssh.com` security-key variants
- **Install-script test suite no longer trips a pytest-10-removal deprecation (class-scoped fixture as instance method)** ([#691](https://github.com/vig-os/devcontainer/issues/691))
  - `TestInstallScriptIntegration.install_workspace` was a class-scoped fixture defined as an instance method, which pytest 9 flags with `PytestRemovedIn10Warning` and pytest 10 removes — a future `pytest` bump would then error at collection and take out the whole install-script suite. Converted it to a `@staticmethod` (it never used `self`), preserving the class-scope "run `install.sh` once per class" behaviour; verified with `-W error::pytest.PytestRemovedIn10Warning`
- **`just build` no longer fails on dev-shell-only podman hosts (missing containers `policy.json`)** ([#685](https://github.com/vig-os/devcontainer/issues/685))
  - On a NixOS host that gets `podman` purely from the flake dev-shell (no `virtualisation.containers` module), no signature-verification `policy.json` exists at `/etc/containers/policy.json` or `~/.config/containers/policy.json`, so `podman load` (`just build`) failed even though `nix build` and the advisory `podman info` check (`just init`) were green
  - `just init` now ensures the user-level `~/.config/containers/policy.json` with the standard permissive default (`{ "default": [ { "type": "insecureAcceptAnything" } ] }`, the same content `containers-common` / the NixOS module ship); the write is idempotent and never overwrites a system or user policy. Documented in `docs/NIX.md`
- **`just init` no longer fails on NixOS hosts (uv downloaded a CPython NixOS cannot execute)** ([#683](https://github.com/vig-os/devcontainer/issues/683))
  - The flake dev-shell carried no Python and let the nixpkgs `uv` fetch a managed CPython — a generic, dynamically-linked ELF a NixOS host cannot execute out of the box (no FHS `ld-linux`) — so `uv sync` (`just init`) aborted on NixOS hosts while FHS hosts were unaffected
  - `mkProjectShell` now pins a Nix store CPython via `UV_PYTHON` and sets `UV_PYTHON_DOWNLOADS=never`, so the dev-shell builds the venv from a store interpreter (patched to the store loader) that runs on both NixOS and FHS hosts instead of a downloaded one
  - CI keeps its managed-download path (`UV_PYTHON_DOWNLOADS_JSON_URL`) and does **not** receive `UV_PYTHON`: the `provision-via-flake` jobs run outside `nix develop` on an FHS runner, where a Nix store interpreter cannot load pre-commit's manylinux-wheel C extensions (`libstdc++.so.6`)
  - Added dev-shell tests asserting `UV_PYTHON_DOWNLOADS=never` and `UV_PYTHON` pinned to a runnable Nix store CPython 3.14
- **Nix image no longer scaffolds dangling, read-only symlinks into a new workspace** ([#664](https://github.com/vig-os/devcontainer/issues/664))
  - The Nix-built image bakes the workspace template as read-only `/nix/store` symlinks (how `buildLayeredImage` represents the layer); `init-workspace.sh` now rsyncs with `--copy-links` and `chmod -R u+w "$WORKSPACE_DIR"`, so a scaffolded workspace gets real, writable files instead of symlinks that dangle on the host (and the placeholder `sed -i` no longer fails on read-only files). No-op on the Debian image
  - Added a static bats guard (scaffold rsync uses `--copy-links`; workspace made writable) and a behavioural step in `nix-image.yml` that scaffolds via the real Nix image and asserts no dangling symlinks — the install/integration suite otherwise only exercises the Debian image
- **`just wt-start` no longer aborts on its helper-CLI prerequisite check** ([#657](https://github.com/vig-os/devcontainer/issues/657))
  - `derive-branch-summary` now handles `-h`/`--help` (prints usage, exits 0) instead of treating the flag as an issue title and failing; the worktree launcher probes availability with `--help`, so the bug blocked worktree creation entirely
- **CONTRIBUTE prerequisites now document the direnv shell hook** ([#633](https://github.com/vig-os/devcontainer/issues/633))
  - The `direnv` prerequisite promised the dev-shell "loads automatically on `cd`" but never documented installing direnv's shell hook (`eval "$(direnv hook bash)"`), the step that behaviour depends on. Without the hook, `direnv allow` still succeeds yet the flake never activates on `cd` and host tooling (e.g. an old system Node) is used with no warning. Documented the hook in the prerequisites table and as a fast-path note, with `nix develop` as the hook-free fallback
- **Workspace python interpreter pointed at the dead `/opt/venv` path** ([#706](https://github.com/vig-os/devcontainer/issues/706))
  - The synced `.vscode/settings.json` rewrote `python.defaultInterpreterPath` to `/opt/venv/bin/python3`, which no longer exists on the Nix image, breaking the VS Code interpreter for downstream projects
  - The interpreter now stays workspace-relative (`${workspaceFolder}/.venv/bin/python3`), matching the `uv`-created `.venv` in the opened project

### Security

- **Nightly vulnix scan hardened against NVD instability; 2026-07 CVE batch triaged** ([#639](https://github.com/vig-os/devcontainer/issues/639))
  - The scan step now survives vulnix's advisory exit codes under the runner's default errexit shell, caches the ~122 MB NVD database on a weekly `actions/cache` key (warm runs fetch only the ~3 MB `modified` feed), retries throttled fetches with backoff, accepts a run only when the findings JSON is valid (a scanner crash previously masqueraded as "whitelisted findings"), and uploads the findings artifact `if: always()`. The pinned `packages.vulnix` patches upstream's hardcoded 10 s NVD fetch timeout to 60 s ([nix-community/vulnix#171](https://github.com/nix-community/vulnix/issues/171))
  - Eight HIGH/CRITICAL CVEs published after the 2026-06-23 baseline (libssh2, socat, libxml2, gzip, fzf, jq) were triaged online against NVD/upstream/nixpkgs branch state and accepted into `.vulnixignore` with staggered 30–60-day expiries: none is fixable by a rev advance today (fixes sit in nixpkgs staging or are unreleased upstream) and none has a realistic attack path in a single-user interactive dev container (details per entry in the register)
- **Bake explicit `substituters`/`trusted-public-keys` instead of `accept-flake-config = true`** ([#773](https://github.com/vig-os/devcontainer/issues/773))
  - The baked `/etc/nix/nix.conf` no longer sets `accept-flake-config = true`, which made any in-container `nix run github:attacker/flake` silently accept that flake's `substituters`/`trusted-public-keys` — a cache-redirection supply-chain trapdoor. The trusted caches are now pinned explicitly (`substituters = https://cache.nixos.org https://vig-os.cachix.org` with their public `trusted-public-keys`) so normal builds still substitute from them, while a foreign flake's `nixConfig` requires a per-invocation `--accept-flake-config`
- **Drop the piscina CVE ignore tied to `cursor-agent`** ([#628](https://github.com/vig-os/devcontainer/issues/628))
  - Removed the `CVE-2026-55388` (piscina) `.trivyignore` entry, which only existed for the now-removed `cursor-agent` CLI
- **vulnix gate fails loud on unscored CVEs and scanner crashes** ([#755](https://github.com/vig-os/devcontainer/issues/755))
  - `vulnix-gate` now blocks on a CVE with no CVSS v3 base score (unknown severity is failed loud, not silently skipped); only sub-threshold *scored* CVEs remain awareness-only
  - The nightly `security-scan` step no longer wraps the vulnix scan in `|| true`: it tolerates only vulnix's scan-ran exit codes (≤ 2) and fails the job on any higher code, so a scanner crash can no longer masquerade as an empty, clean result
- **Hard vulnix CVE gate on the release publish path** ([#753](https://github.com/vig-os/devcontainer/issues/753))
  - The release workflow now runs a `vulnix-gate` job (the same `vulnix-gate` / `.vulnixignore` check as the nightly `security-scan`, built from the finalized release commit's image closure) that the `publish` job `needs:`, so a release can no longer ship an image carrying an unexcepted HIGH/CRITICAL CVE that nightly vulnix would have blocked. Previously the only CVE gate on the publish path was the per-arch Trivy step, which is largely dark on a Nix image. Wired into the rollback trigger alongside the other pre-publish jobs (Refs [#639](https://github.com/vig-os/devcontainer/issues/639))

## [0.3.9](https://github.com/vig-os/devcontainer/releases/tag/0.3.9) - 2026-06-23

### Fixed

- **Stop promote-release cleanup from orphaning RC draft pre-releases** ([#623](https://github.com/vig-os/devcontainer/issues/623))
  - The cleanup step deleted RC draft pre-releases with `gh release delete <tag>`, which cannot resolve a draft, then deleted the git RC tag anyway — stranding the draft and making it undiscoverable on later runs (the loop was seeded from git tags)
  - Cleanup now enumerates RC draft pre-releases from the releases list, deletes them by release id, removes a git RC tag only when no release is attached, and fails loudly if any RC draft survives — also reclaiming drafts whose tag was already removed by an earlier partial run

## [0.3.8](https://github.com/vig-os/devcontainer/releases/tag/0.3.8) - 2026-06-22

### Fixed

- **Prevent prepare-release from branching `release/X.Y.Z` at the pre-freeze dev SHA** ([#617](https://github.com/vig-os/devcontainer/issues/617))
  - The "Create release branch from dev" step now polls dev until it advances past the captured pre-freeze SHA before branching, and hard-fails if it never does, closing a read-after-write race that could create a release branch missing the `## [X.Y.Z] - TBD` freeze
- **Make smoke-test dispatch idempotent across candidate→final on one base version** ([#612](https://github.com/vig-os/devcontainer/issues/612))
  - `prepare-changelog finalize` is now a no-op when the version heading is already dated, instead of erroring
  - `prepare-changelog prepare` folds an existing same-version heading back into a single `## [X.Y.Z] - TBD` section instead of stacking a duplicate
  - New `prepare-changelog reset-version <version>` command reverts a dated heading back to `- TBD` (idempotent); the smoke-test dispatch template runs it at dispatch start and scopes its deploy-seed check to the `Unreleased` section
- **Fix release PR body truncation when changelog bullets quote a version heading** ([#620](https://github.com/vig-os/devcontainer/issues/620))
  - The "Extract CHANGELOG content for PR body" step now anchors its `sed` range to start-of-line headings, so an inline backtick-quoted heading inside a bullet no longer ends the range early

## [0.3.7](https://github.com/vig-os/devcontainer/releases/tag/0.3.7) - 2026-06-22

### Changed

- **Consolidate Renovate dependency updates (588, 589, 606, 607)** ([#588](https://github.com/vig-os/devcontainer/pull/588), [#589](https://github.com/vig-os/devcontainer/pull/589), [#606](https://github.com/vig-os/devcontainer/pull/606), [#607](https://github.com/vig-os/devcontainer/pull/607))
  - Update `actions/checkout` to `v7.0.0`, `taiki-e/install-action` digest to `ab08a3b`, `astral-sh/setup-uv` to `0.11.23`, and the `aquasecurity/trivy-action` scanner to `v0.71.2`
  - Bump Python deps: `pytest` 9.1.1, `ruff` 0.15.18 (root); `numpy` 2.5.0, `scipy` 1.18.0 (workspace template); lockfile refreshed

### Fixed

- **Prune RC draft pre-releases in promote cleanup** ([#600](https://github.com/vig-os/devcontainer/issues/600))
  - Cleanup now deletes `X.Y.Z-rcN` draft pre-releases (and their now-orphaned tags); guarded to never touch published releases

### Security

- **Consolidate container-image vulnerability scanning to a single source of truth** ([#604](https://github.com/vig-os/devcontainer/issues/604))
  - PR CI Trivy is now a blocking gate only (fail on fixable HIGH/CRITICAL) and no longer uploads SARIF to the Security tab
  - The nightly scheduled scan of the published `:latest` image (`container-image-latest`) is now the single authoritative scan for the GitHub Security tab, ending duplicate/stale alert categories
  - Dismissed orphaned `container-image-scheduled` and stale `container-image` code-scanning alerts that could no longer auto-close

## [0.3.6](https://github.com/vig-os/devcontainer/releases/tag/0.3.6) - 2026-06-19

### Changed

- **Migrate `actions/create-github-app-token` to `client-id`** ([#576](https://github.com/vig-os/devcontainer/issues/576))
  - Replace deprecated `app-id` input with `client-id` across root, workspace template, and smoke-test workflows
  - Requires org-level `COMMIT_APP_CLIENT_ID` and `RELEASE_APP_CLIENT_ID` secrets (GitHub App Client ID, not numeric App ID)
- **Consolidate Renovate dependency updates (586–589)** ([#586](https://github.com/vig-os/devcontainer/pull/586), [#587](https://github.com/vig-os/devcontainer/pull/587), [#588](https://github.com/vig-os/devcontainer/pull/588), [#589](https://github.com/vig-os/devcontainer/pull/589))
  - Bump `python:3.14-slim-bookworm` base image to multi-arch index digest `sha256:7e2f304…`
  - Update `taiki-e/install-action` digest to `bafb217`, `astral-sh/setup-uv` to `0.11.21`, and other GitHub Actions minor/patch versions
  - Bump `requires-python` to `==3.14.6` and Python deps: `pytest` 9.1.0, `ruff` 0.15.17, `github-backup` 0.63.0 (lockfile refreshed)

### Fixed

- **Smoke-test `prepare-release` failed on empty Unreleased section** ([#597](https://github.com/vig-os/devcontainer/issues/597))
  - The smoke-test fixture has no hand-authored changelog entries, so each release freeze left `## Unreleased` empty and the downstream `prepare-release` gate rejected it ("Unreleased section has no entries")
  - The deploy step in `repository-dispatch.yml` now seeds a deploy entry into `## Unreleased` when it is empty, so the smoke-test release pipeline can always proceed
- **`sync-main-to-dev` could silently drop the fresh `## Unreleased` scaffold** ([#590](https://github.com/vig-os/devcontainer/issues/590))
  - `prepare-release` no longer strips `## Unreleased` from the release branch, so `main` keeps an empty `## Unreleased` above the dated release (matching `dev`)
  - With the section present on both branches it is stable common context in the `main`↔`dev` merge base, so the sync merge preserves it cleanly instead of resolving in `main`'s favour and dropping it
  - Applied to both the canonical workflow and the workspace template so adopters (e.g. `part-registry`) inherit the fix
- **`devcontainer-upgrade` / install URL 404s** ([#591](https://github.com/vig-os/devcontainer/issues/591))
  - Replace the unhosted `vig-os.github.io/devcontainer/install.sh` Pages URL with the canonical `raw.githubusercontent.com/vig-os/devcontainer/main/install.sh` already used in `README.md`
  - Pipe the installer to `bash` instead of `sh` (the script has a `#!/bin/bash` shebang and uses bashisms), matching the canonical form
  - Fixes the actual `just devcontainer-upgrade` host command plus error hints, the version-check upgrade nag, smoke-test install docs, and `install.sh` usage/`--help` output

- **GHCR RC artifacts never pruned after promote-release** ([#583](https://github.com/vig-os/devcontainer/issues/583))
  - Switch GHCR package-version deletes to `GITHUB_TOKEN` with repo Admin on the `devcontainer` package (one-time Manage Actions access grant)
  - Replace blanket `sha256-*` deletion with digest-aware selection that prunes RC images and matching RC cosign signatures only
  - Fail the cleanup step loudly when deletes fail or RC tags remain (job still uses `continue-on-error`)

## [0.3.5](https://github.com/vig-os/devcontainer/releases/tag/0.3.5) - 2026-06-10

### Changed

- **Consolidate Renovate dependency updates** ([#550](https://github.com/vig-os/devcontainer/issues/550))
  - Python 3.12 → 3.14.5 (`Containerfile`, `requires-python`, and lockfile)
  - CI runners `ubuntu-22.04` → `24.04` and Node.js 22 → 24
  - GitHub Actions major bumps: `setup-node` v6, `setup-uv` v8, `github-script` v9
  - SHA-pinned digest updates for checkout, codeql, create-github-app-token, and taiki-e/install-action
  - Pin Python, npm, and workspace template dependencies to exact versions ([#530](https://github.com/vig-os/devcontainer/issues/530))
  - `@devcontainers/cli` 0.87.0 ([#538](https://github.com/vig-os/devcontainer/issues/538))

- **Bump expected tool versions in image tests**
  - `gh` 2.92 → 2.93, `just` 1.50 → 1.52, `cargo-binstall` 1.18 → 1.20 to match latest upstream releases

- **Consolidate Renovate dependency updates (553–556)** ([#553](https://github.com/vig-os/devcontainer/issues/553), [#554](https://github.com/vig-os/devcontainer/issues/554), [#555](https://github.com/vig-os/devcontainer/issues/555), [#556](https://github.com/vig-os/devcontainer/issues/556))
  - Pin `pytest` to 9.0.3, bump `pytest-cov` to 7.1.0, `rich` to 15.0.0
  - Bump `github-backup` to 0.62.1, `pre-commit` to 4.6.0, `ruff` to 0.15.16, `pip-licenses` to 5.5.5
  - Bump expected `pre-commit` version in image tests to 4.6
  - Bump `actions/dependency-review-action` to v5.0.0

### Fixed

- **Renovate PR CI gates expired or broken** ([#550](https://github.com/vig-os/devcontainer/issues/550))
  - Renovate changelog workflow now runs under `bash` so `set -euo pipefail` works inside the container
  - Taplo lint hook no longer fetches remote schema catalogs (fetch started failing in taplo 0.10)
  - Renewed dependency-review allow-list exception for bats-file false positive (`GHSA-wvrr-2x4r-394v`)

- **Image tests red on stale cargo-binstall pin** ([#557](https://github.com/vig-os/devcontainer/issues/557))
  - Bump expected `cargo-binstall` to 1.20 to match the latest upstream release the image installs

- **arm64 release build failed with "exec format error"** ([#578](https://github.com/vig-os/devcontainer/issues/578))
  - Restore the multi-arch index digest for `python:3.14-slim-bookworm` (`sha256:a9bee155…`); the previous bump pinned the amd64-only child manifest, so the arm64 build pulled an amd64 image and the first `RUN` died with `exec /bin/sh: exec format error`
  - Document in `Containerfile` that manual base-image pins must use the index digest, never a per-platform child manifest

### Security

- **Accept Debian won't-fix LOW CVEs in .trivyignore** ([#566](https://github.com/vig-os/devcontainer/issues/566))
  - Document 78 unfixed LOW Debian OS-package CVEs from the next-release image with shared risk note and 2026-12-01 expiration
  - Add `check-expirations` utility with pre-commit and CI enforcement so expired `.trivyignore` entries fail the pipeline
  - Security tab LOW count drops after the next release refreshes `:latest`

- **Bump base image digest and clear fixable OS-package CVEs** ([#565](https://github.com/vig-os/devcontainer/issues/565))
  - Keep `python:3.14-slim-bookworm` pinned to its multi-arch index digest (`sha256:a9bee155…`)
  - Retain targeted `libgnutls30=3.7.9-2+deb12u7` upgrade (base ships `deb12u6`; fixable GnuTLS CVEs require `deb12u7`)
  - CI Trivy gate passes with zero fixable HIGH/CRITICAL OS findings after rebuild

- **Patch fixable OpenSSL HIGH CVE blocking the 0.3.5 release** ([#580](https://github.com/vig-os/devcontainer/issues/580))
  - Targeted `libssl3`/`openssl` upgrade to `3.0.20-1~deb12u2` (base ships `deb12u1`); clears `CVE-2026-45447` flagged by the release Trivy gate

- **Refresh bundled gh and uv to clear Go and Rust CVEs** ([#564](https://github.com/vig-os/devcontainer/issues/564))
  - Fresh image build pulls latest `gh` v2.93.0 and `uv` v0.11.19, clearing all bundled-tool HIGH findings except one awaiting upstream
  - `uv`/`uvx` Rust crate CVEs (including `rustls-webpki` GHSA-82j2-j2ch-gfr8) no longer reported after rebuild
  - Remaining `gh` Go-stdlib HIGH (CVE-2026-42504) kept in `.trivyignore` until `gh` ships a Go 1.26.4 rebuild

- **Update pytest to v9.0.3** ([#528](https://github.com/vig-os/devcontainer/issues/528))
  - Security patch for pytest dependency bump

- **Remediate nightly scan gate failures on :latest** ([#549](https://github.com/vig-os/devcontainer/issues/549))
  - Patched `libgnutls30` to `3.7.9-2+deb12u7` for fixable GnuTLS CVEs (retained across the 3.14 base rebase; see #565)

- **Resolve repo-owned workflow security findings** ([#562](https://github.com/vig-os/devcontainer/issues/562))
  - Split Renovate changelog automation into read-only `pull_request` build + privileged `workflow_run` commit, removing `pull_request_target` and PR-head checkout under elevated permissions (Scorecard `DangerousWorkflowID`)
  - Add GitHub Actions to CodeQL language matrix so stale `actions/missing-workflow-permissions` alerts auto-close on the next default-branch run
  - Add explicit `permissions:` to workspace `release-extension.yml` template; downstream smoke-test updates flow through release re-sync
  - Document accepted OpenSSF Scorecard posture (Fuzzing, CII) and verified branch-protection rulesets in `SECURITY.md`

- **Update vulnerable Python dependencies** ([#563](https://github.com/vig-os/devcontainer/issues/563))
  - Bump `urllib3` 2.7.0, `requests` 2.34.2, `idna` 3.18, `Pygments` 2.20.0 in the repo lockfile
  - Constrain workspace-template jupyter stack to patched versions (`notebook` 7.5.6, `jupyterlab` 4.5.7, `jupyter-server` 2.18.0, `mistune` 3.2.1)

- **Add downstream SECURITY.md template and close smoke-test Scorecard gaps** ([#568](https://github.com/vig-os/devcontainer/issues/568))
  - Add `assets/workspace/SECURITY.md` so generated and smoke-test repos ship a security policy (clears Scorecard `SecurityPolicyID` on the next release re-sync)
  - Document `FuzzingID` and `CIIBestPracticesID` as accepted won't-fix posture in the template policy
  - Document smoke-test-specific accepted findings (branch-protection, code-review, pinned `download-then-run`) in the `assets/smoke-test/` overlay, accepted because the deploy-validation repo runs fully unattended

## [0.3.4](https://github.com/vig-os/devcontainer/releases/tag/0.3.4) - 2026-04-29

### Added

- **Renovate config validation on pull requests** ([#520](https://github.com/vig-os/devcontainer/issues/520))
  - Workflow discovers tracked `renovate*.json` files (excluding `assets/workspace/renovate.json`, whose `extends` uses an unresolved template placeholder) and runs `renovate-config-validator --strict` on the rest when renovate JSON changes
  - `just test-renovate` recipe mirrors the workflow locally and is included in `just test`

### Changed

- **Bump expected tool versions in image tests**
  - `gh` 2.89 → 2.92, `just` 1.49 → 1.50, `cargo-binstall` 1.17 → 1.18 to match the latest upstream releases the image now installs

### Fixed

- **Renovate preset blocked all dependency updates** ([#520](https://github.com/vig-os/devcontainer/issues/520))
  - Split Python `packageRules` so `matchUpdateTypes` and `rangeStrategy` are not combined in one rule; rename `baseBranches` to `baseBranchPatterns`
  - Remove invalid `uv` from `enabledManagers` (`pep621` continues to handle `pyproject.toml` and `uv.lock`)

## [0.3.3](https://github.com/vig-os/devcontainer/releases/tag/0.3.3) - 2026-04-10

### Added

- **Renovate changelog automation** ([#506](https://github.com/vig-os/devcontainer/issues/506))
  - `renovate-changelog-pr` CLI tool parses Renovate PR metadata and inserts Keep-a-Changelog entries under `## Unreleased`
  - `renovate-changelog` workflow runs on `pull_request_target` for `renovate[bot]` PRs in both upstream and workspace template
- **Devcontainer image version pinning** ([#509](https://github.com/vig-os/devcontainer/issues/509))
  - `.vig-os` file at repo root declares `DEVCONTAINER_VERSION` as the single source of truth for CI container image tags
  - `resolve-image` composite action resolves the image tag and validates it exists in GHCR
- **`GITHUB_REPOSITORY` resolution for workspace init** ([#509](https://github.com/vig-os/devcontainer/issues/509))
  - `parse-github-remote-lib.sh` extracts `owner/repo` from HTTPS, SSH, and `git@` GitHub URLs
  - `install.sh` gains `--repo` flag; `init-workspace.sh` replaces `{{GITHUB_REPOSITORY}}` in workspace template files

### Changed

- **Switch from Dependabot to Renovate** ([#509](https://github.com/vig-os/devcontainer/issues/509))
  - Replace `.github/dependabot.yml` with `renovate.json` and shared `renovate-default.json` preset
  - Renovate covers all ecosystems previously tracked (github-actions, pip, npm, docker) plus template directories not reachable by Dependabot
- **Sync workflows run in devcontainer image** ([#509](https://github.com/vig-os/devcontainer/issues/509))
  - `sync-issues` and `sync-main-to-dev` use `resolve-image` and run inside the pinned devcontainer, removing the `setup-env` composite action dependency and the inlined retry helper
  - `sync-main-to-dev` creates sync branches via `git push` instead of the GitHub refs API
- **Smoke-test dispatch triggers promote-release for final releases** ([#511](https://github.com/vig-os/devcontainer/issues/511))
  - Final releases dispatch downstream `promote-release.yml` instead of merging the release PR directly, publishing the draft GitHub Release and satisfying the upstream promote-time downstream gate
  - RC releases wait for release PR required checks but no longer merge the PR to `main`

### Removed

- **Dependabot configuration** ([#509](https://github.com/vig-os/devcontainer/issues/509))
  - Delete `.github/dependabot.yml` and `assets/workspace/.github/dependabot.yml`

### Fixed

- **Promote-release draft release validation** ([#507](https://github.com/vig-os/devcontainer/issues/507))
  - Use the paginated releases list API with jq instead of `GET /releases/tags/{tag}`, which returns 404 for draft releases
  - Apply the same release lookup for RC git tag cleanup in upstream and workspace `promote-release.yml`
- **Promote-release validate job cannot see draft releases** ([#517](https://github.com/vig-os/devcontainer/issues/517))
  - Elevate `validate` job permissions to `contents: write` so the token has push-level access required by the GitHub API to list draft releases
  - Use `github.token` instead of the release app token for the draft release check in workspace `promote-release.yml`

### Security

- **Nightly Trivy gate remediation (OpenSSL, gh, typos)** ([#512](https://github.com/vig-os/devcontainer/issues/512))
  - Pin `python:3.12-slim-bookworm` to current digest and add targeted `libssl3`/`openssl` upgrade to `3.0.19-1~deb12u2` (CVE-2026-28390, CVE-2026-31790)
  - Refresh `.trivyignore`: drop resolved gh/docker-cli and gRPC entries; add Go stdlib and typos-related suppressions plus `jwt-token` false positive
  - Suppress unfixable base-image CVEs: ncurses (CVE-2025-69720), SQLite (CVE-2025-7458), systemd (CVE-2026-29111), zlib/minizip (CVE-2023-45853)

## [0.3.2](https://github.com/vig-os/devcontainer/releases/tag/0.3.2) - 2026-04-08

### Added

- **Downstream `promote-release.yml` workspace template** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Add `assets/workspace/.github/workflows/promote-release.yml` as the counter-party to root `promote-release.yml`: validate draft release and release PR, publish the release, merge to `main`, best-effort git RC tag cleanup (no GHCR/cosign/smoke-test gate)
  - Document in `docs/DOWNSTREAM_RELEASE.md` and align `docs/RELEASE_CYCLE.md` Phase 5 for consumer vs upstream paths
- **Optional draft pre-release for downstream release candidates** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Workspace `release.yml` adds `create-release` (`workflow_dispatch`, default `false`); `release-publish.yml` creates a draft GitHub pre-release only when set for `candidate` runs
  - Smoke-test `repository-dispatch.yml` passes `create-release=true` when triggering downstream `release.yml`
  - `just publish-candidate` forwards `create-release` in `justfile.gh` and the workspace template copy

### Changed

- **RELEASE_APP permissions and GHCR cleanup token model** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Document Packages read/write on the org for `promote-release` cleanup, align the app table in `docs/RELEASE_CYCLE.md`, and explain why cleanup uses the GitHub App token instead of `GITHUB_TOKEN`
- **Promote-release cleans up stale RC artifacts after merge** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Best-effort job deletes GHCR package versions for `${VERSION}-rc*` and `sha256-*`-only orphans, and deletes remote git RC tags for that base version when no GitHub Release exists; does not fail the workflow on error
- **Downstream release helper recipes via GitHub justfile import** ([#373](https://github.com/vig-os/devcontainer/issues/373))
  - Move `prepare-release`, `finalize-release`, `publish-candidate`, and `reset-changelog` into `justfile.gh` so downstream workspace templates expose these release helpers by default
  - Keep root recipe availability (including `pull`) through `import 'justfile.gh'` while consolidating release helper ownership in the GitHub-focused recipe file; the workspace template copy omits the `pull` recipe
- **Split final release into publish and promote phases** ([#456](https://github.com/vig-os/devcontainer/issues/456))
  - Final `release.yml` publishes versioned GHCR tags and a draft GitHub Release but no longer updates `:latest`
  - New `promote-release.yml` runs after downstream smoke-test publishes its final release: updates `:latest`, publishes the draft release, merges the release PR to `main`
  - Add `just promote-release` in `justfile.gh` (and workspace template copy)
- **Smoke-test dispatch fails fast when deploy PR checks fail** ([#381](https://github.com/vig-os/devcontainer/issues/381))
  - `wait-deploy-merge` in `assets/smoke-test/.github/workflows/repository-dispatch.yml` exits as soon as all required checks have completed with failures instead of waiting for the merge poll timeout (`gh pr checks --required`)
- **Scheduled security scan pulls GHCR `:latest` instead of rebuilding** ([#461](https://github.com/vig-os/devcontainer/issues/461))
  - Runs nightly at 05:00 UTC, pulls the published image, gates on fixable HIGH/CRITICAL vulnerabilities, auto-creates a deduplicated GitHub issue on failure, and uploads SARIF under `container-image-latest`
- **Dependabot dependency update batch** ([#474](https://github.com/vig-os/devcontainer/pull/474))
  - Bump `github/codeql-action` from `4.34.1` to `4.35.1`
  - Bump `sigstore/cosign-installer` from `4.1.0` to `4.1.1`
- **Dependabot dependency update batch** ([#488](https://github.com/vig-os/devcontainer/pull/488), [#489](https://github.com/vig-os/devcontainer/pull/489))
  - Bump `@devcontainers/cli` from `0.84.1` to `0.85.0`
  - Bump `docker/login-action` from `4.0.0` to `4.1.0`
- **Simplify `just pull` in `justfile.gh`** ([#482](https://github.com/vig-os/devcontainer/issues/482))
  - Pull `ghcr.io/vig-os/devcontainer` by tag; drop redundant shell fallback, per-recipe `repo` argument, and unused `REGISTRY_TEST` TLS path (imported `justfile.gh` cannot reference root `repo`)
- **prepare-changelog finalize adds GitHub release link to version headings** ([#496](https://github.com/vig-os/devcontainer/issues/496))
  - `finalize_release_date` writes `## [X.Y.Z](https://github.com/owner/repo/releases/tag/X.Y.Z) - date`; repository slug comes from `GITHUB_REPOSITORY` (set in Actions) or from `prepare-changelog finalize ... --github-repository owner/repo`
  - `unprepare` recognizes linked `## [semver](url) - …` headings

### Removed

- **One-time GHCR/git RC prune script** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Remove `scripts/prune-ghcr-tags.sh`; RC and `sha256-*` orphan cleanup remains in root `promote-release.yml`
- **Downstream RC pre-release gate from release validate job** ([#463](https://github.com/vig-os/devcontainer/issues/463))
  - Removed dead `if: false` steps from `release.yml`; downstream final release is verified only in `promote-release.yml` before promote
- **Nightly full CI schedule from `ci.yml`** ([#492](https://github.com/vig-os/devcontainer/issues/492))
  - Remove the `schedule` trigger and schedule-only checkout overrides; CI remains on pull requests and `workflow_dispatch` only
  - Nightly GHCR `:latest` scan in `security-scan.yml` is unchanged

### Fixed

- **Prepare-release changelog commits silently skipped due to FILE_PATHS delimiter mismatch** ([#483](https://github.com/vig-os/devcontainer/issues/483))
  - Change `FILE_PATHS` from space-separated to comma-separated in all `commit-action` steps of `prepare-release.yml` so the action correctly commits both `CHANGELOG.md` and `assets/workspace/.devcontainer/CHANGELOG.md`
  - Join finalization changed files with commas in `release.yml` (`Collect finalization files`) so `commit-action` receives multiple paths correctly
- **`publish-candidate` recipe sends unknown `create-release` input** ([#479](https://github.com/vig-os/devcontainer/issues/479))
  - Remove `create-release` parameter and `-f` flag from upstream `justfile.gh`; the input was added to the downstream workflow only but the recipe was updated in both places
- **Image tests expect current `just` minor** ([#479](https://github.com/vig-os/devcontainer/issues/479))
  - Align `EXPECTED_VERSIONS["just"]` with the latest `just` release installed by the Containerfile (1.49.x)
- **Git commit now falls back to nano when editor config is unusable** ([#383](https://github.com/vig-os/devcontainer/issues/383))
  - `setup-git-conf.sh` now validates the effective Git editor and sets `core.editor=nano` only when the configured editor is missing or invalid in-container
  - Add integration regression coverage to ensure invalid editor settings are corrected during setup
- **Release finalize no longer races sync-issues; CHANGELOG TBD verified after reset** ([#455](https://github.com/vig-os/devcontainer/issues/455))
  - Run `sync-issues` after capturing finalize SHA so downstream build/publish use the finalized commit
  - Fail finalize if `CHANGELOG.md` still contains `## [version] - TBD` after `git reset --hard`
- **generate-docs pre-commit runs when CHANGELOG.md changes** ([#455](https://github.com/vig-os/devcontainer/issues/455))
  - Keeps README “Latest Version” and other generated docs aligned with the changelog
- **prepare-release tolerates GitHub API ref propagation and reliable CHANGELOG rollback** ([#453](https://github.com/vig-os/devcontainer/issues/453))
  - Poll until the new release branch ref resolves before `commit-action` commits to it
  - Fetch dev `CHANGELOG.md` by resolved commit SHA during rollback so Contents API staleness does not skip the rollback commit
- **sync-main-to-dev sync job no longer depends on dev's setup-env** ([#459](https://github.com/vig-os/devcontainer/issues/459))
  - Inline the same `retry` shell helper used by `setup-env` so the job works when `main`'s workflow expects helpers not yet on `dev`
- **CI container build avoids shared-runner Docker Hub rate limits** ([#473](https://github.com/vig-os/devcontainer/issues/473))
  - `build-image` logs in to `docker.io` before `setup-buildx-action` when `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets are set; `ci.yml` and `release.yml` pass them
  - Omitting secrets (e.g. forks) keeps prior anonymous-pull behavior
- **Release finalize commit blocked by Release protection ruleset** ([#487](https://github.com/vig-os/devcontainer/issues/487))
  - Generate a dedicated Commit App token (`COMMIT_APP_ID`) for the `commit-action` step in the `finalize` job of `release.yml`, matching the pattern used by `prepare-release.yml` and other workflows; the previous Release App token lacked ruleset bypass
- **Release finalize installs just for doc generation** ([#494](https://github.com/vig-os/devcontainer/issues/494))
  - Remove `install-just: 'false'` from the finalize job `setup-env` step so `docs/generate.py` can run `just --list`
  - `get_just_help()` exits non-zero on failure instead of writing placeholder content into generated docs
- **Release rollback and CI `retry` exit codes** ([#500](https://github.com/vig-os/devcontainer/issues/500))
  - `retry` shell helper now propagates the command's non-zero exit code when all attempts fail
  - Release rollback creates a fast-forward revert commit via the Git API instead of force-pushing, compatible with branch protection on `release/*`
  - Rollback Git Data API steps authenticate with the Commit app token (same as finalize) so protected `release/*` ref updates are not blocked
  - Canonical `retry()` implementation lives in `.github/scripts/retry.sh`; `setup-env` and BATS source it so CI and tests stay aligned (`sync-main-to-dev.yml` keeps an inline copy documented as in sync)
- **Release rollback restores release PR body after finalize** ([#502](https://github.com/vig-os/devcontainer/issues/502))
  - `rollback` job in `release.yml` restores the PR description from pre-finalization `CHANGELOG.md` (TBD / prepare-release format) using RELEASE_APP when `release_kind` is final, after branch rollback; failure issue and job summary report the step outcome
- **Final release notes extraction after linked changelog headings** ([#504](https://github.com/vig-os/devcontainer/issues/504))
  - Publish job `awk` matches `## [VERSION]` prefix so finalized `## [X.Y.Z](url) - date` headings produce GitHub Release notes (regression after prepare-changelog linked headings in #496)

### Security

- **Nightly vulnerability gate for published container image** ([#461](https://github.com/vig-os/devcontainer/issues/461))
  - Scheduled security scan now fails on fixable HIGH/CRITICAL CVEs and auto-files a GitHub issue, replacing the previous non-blocking weekly scan

## [0.3.1](https://github.com/vig-os/devcontainer/releases/tag/0.3.1) - 2026-03-26

### Added

- **Split downstream release workflow with project-owned extension hook** ([#326](https://github.com/vig-os/devcontainer/issues/326))
  - Add local `workflow_call` release phases (`release-core.yml`, `release-publish.yml`) and a lightweight `release.yml` orchestrator in `assets/workspace/.github/workflows/`
  - Add `release_kind` support with candidate mode (`X.Y.Z-rcN`) and final mode (`X.Y.Z`) in downstream release workflows
  - Candidate mode now auto-computes the next RC tag, skips CHANGELOG finalization/sync-issues, and publishes a GitHub pre-release
  - Add project-owned `release-extension.yml` stub and preserve it during `init-workspace.sh --force` upgrades
  - Add `validate-contract` composite action for single-source contract version validation
  - Add downstream release contract documentation and GHCR extension example in `docs/DOWNSTREAM_RELEASE.md`
- **`jq` in devcontainer image** ([#425](https://github.com/vig-os/devcontainer/issues/425))
  - Install the `jq` CLI in the GHCR image so containerized workflows (e.g. `release-core` validate / downstream Release Core) can pipe JSON through `jq`

### Changed

- **Dependabot dependency update batch** ([#302](https://github.com/vig-os/devcontainer/pull/302), [#303](https://github.com/vig-os/devcontainer/pull/303), [#305](https://github.com/vig-os/devcontainer/pull/305), [#306](https://github.com/vig-os/devcontainer/pull/306), [#307](https://github.com/vig-os/devcontainer/pull/307), [#308](https://github.com/vig-os/devcontainer/pull/308), [#309](https://github.com/vig-os/devcontainer/pull/309))
  - Bump `@devcontainers/cli` from `0.81.1` to `0.84.0` and `bats-assert` from `v2.2.0` to `v2.2.4`
  - Bump GitHub Actions: `actions/download-artifact` (`4.3.0` -> `8.0.1`), `actions/github-script` (`7.1.0` -> `8.0.0`), `actions/attest-build-provenance` (`3.0.0` -> `4.1.0`), `actions/checkout` (`4.3.1` -> `6.0.2`)
  - Bump release workflow action pins: `sigstore/cosign-installer` (`4.0.0` -> `4.1.0`) and `anchore/sbom-action` (`0.22.2` -> `0.23.1`)
- **Dependabot dependency update batch** ([#314](https://github.com/vig-os/devcontainer/pull/314), [#315](https://github.com/vig-os/devcontainer/pull/315), [#316](https://github.com/vig-os/devcontainer/pull/316), [#317](https://github.com/vig-os/devcontainer/pull/317))
  - Bump GitHub Actions: `actions/attest-sbom` (`3.0.0` -> `4.0.0`), `actions/upload-artifact` (`4.6.2` -> `7.0.0`), `actions/create-github-app-token` (`2.2.1` -> `3.0.0`)
  - Bump `docker/login-action` from `3.7.0` to `4.0.0`
  - Bump `just` minor version from `1.46` to `1.47`
- **Node24-ready GitHub Actions pin refresh for shared composite actions** ([#321](https://github.com/vig-os/devcontainer/issues/321))
  - Update Docker build path pins in `build-image` (`docker/setup-buildx-action`, `docker/metadata-action`, `docker/build-push-action`) to Node24-compatible releases
  - Set `setup-env` default Node runtime to `24` and upgrade `actions/setup-node`
  - Align test composite actions with newer pins (`actions/checkout`, `actions/cache`, `actions/upload-artifact`)
- **Smoke-test dispatch payload now carries source run traceability metadata** ([#289](https://github.com/vig-os/devcontainer/issues/289))
  - Candidate release dispatches now include source repo/workflow/run/SHA metadata plus a deterministic `correlation_id`
  - Smoke-test dispatch receiver logs normalized source context, derives source run URL when possible, and writes it to workflow summary output
  - Release-cycle docs now define required vs optional dispatch payload keys and the future callback contract path for `publish-candidate`
- **Smoke-test repository dispatch now runs for final releases too** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - `release.yml` now triggers the existing smoke-test dispatch contract for both `candidate` and `final` release kinds
  - Final release summaries and release-cycle documentation now reflect dispatch behavior for both release modes
- **Workspace CI templates now use a single container-based workflow** ([#327](https://github.com/vig-os/devcontainer/issues/327))
  - Consolidate `assets/workspace/.github/workflows/ci.yml` as the canonical CI workflow and remove the obsolete `ci-container.yml` template
  - Extract reusable `assets/workspace/.github/actions/resolve-image` and run workspace release tests in the same containerized workflow model
  - Update smoke-test and release-cycle documentation to reference the single CI workflow contract
- **Final release now requires downstream RC pre-release gate** ([#331](https://github.com/vig-os/devcontainer/issues/331))
  - Add upstream final-release validation that requires a downstream GitHub pre-release for the latest published RC tag
  - Move smoke-test dispatch to a dedicated release job and include `release_kind` in the dispatch payload
  - Add downstream `repository-dispatch.yml` template that runs smoke tests and creates pre-release/final release artifacts
- **Ship changelog into workspace payload and smoke-test deploy root** ([#333](https://github.com/vig-os/devcontainer/issues/333))
  - Sync canonical `CHANGELOG.md` into both workspace root and `.devcontainer/` template paths
  - Smoke-test dispatch now copies `.devcontainer/CHANGELOG.md` to repository root so deploy output keeps a root changelog
- **Final release now publishes a GitHub Release with finalized notes** ([#310](https://github.com/vig-os/devcontainer/issues/310))
  - Add a final-only publish step in `.github/workflows/release.yml` that creates a GitHub Release for `X.Y.Z`
  - Source GitHub Release notes from the finalized `CHANGELOG.md` section and fail the run if notes extraction or release publishing fails
- **Release dispatch and publish ordering hardened for 0.3.1** ([#336](https://github.com/vig-os/devcontainer/issues/336))
  - Make smoke-test dispatch fire-and-forget in `.github/workflows/release.yml` and decouple rollback from downstream completion timing
  - Add bounded retries to the final-release downstream RC pre-release gate API check
  - Move final GitHub Release creation to the end of publish so artifact publication/signing completes before release object creation
  - Add concurrency control to `assets/smoke-test/.github/workflows/repository-dispatch.yml` to prevent overlapping dispatch races
  - Handle smoke-test dispatch failures with a targeted issue while avoiding destructive rollback after publish artifacts are already released
- **Redesigned smoke-test dispatch release orchestration** ([#358](https://github.com/vig-os/devcontainer/issues/358))
  - Replace premature `publish-release` behavior with full downstream orchestration: deploy-to-dev merge gate, `prepare-release.yml`, release PR readiness/approval, and `release.yml` dispatch polling
  - Add upstream failure issue reporting with job-phase results and cleanup guidance when dispatch orchestration fails
- **Smoke-test release orchestration now runs as two phases** ([#402](https://github.com/vig-os/devcontainer/issues/402))
  - Keep `repository-dispatch.yml` focused on deploy/prepare/release-PR readiness and move release dispatch to a dedicated merged-PR workflow (`on-release-pr-merge.yml`)
  - Add release-kind labeling and auto-merge enablement for release PRs, and keep upstream failure notifications in both phases
  - Remove release-branch upstream `CHANGELOG.md` sync from `repository-dispatch.yml` (previously added in [#358](https://github.com/vig-os/devcontainer/issues/358))
- **Dependabot dependency update batch** ([#414](https://github.com/vig-os/devcontainer/pull/414))
  - Bump `github/codeql-action` from `4.32.6` to `4.34.1` and `anchore/sbom-action` from `0.23.1` to `0.24.0`
  - Bump `actions/cache` restore/save pins from `5.0.3` to `5.0.4` in `sync-issues.yml`
- **Dependabot dependency update batch** ([#413](https://github.com/vig-os/devcontainer/pull/413))
  - Bump `@devcontainers/cli` from `0.84.0` to `0.84.1`
- **cursor-agent install is now resilient to CDN failures** ([#434](https://github.com/vig-os/devcontainer/issues/434))
  - Retries 3 times with backoff before giving up
  - Build succeeds without cursor-agent when Cursor's CDN is unavailable
- **Immutable GitHub releases, tag rulesets, and forward-fix policy** ([#446](https://github.com/vig-os/devcontainer/issues/446))
  - Final releases create a **draft** GitHub Release for human review before publishing; rollback no longer deletes remote tags
  - Release workflows skip redundant tag push when the tag already matches the finalized commit; workspace `release-core` / `release-publish` and smoke-test failure guidance updated accordingly
  - Document tag rulesets, immutable releases, and recovery in `docs/RELEASE_CYCLE.md`, `docs/DOWNSTREAM_RELEASE.md`, and `docs/CROSS_REPO_RELEASE_GATE.md`
- **Container image tests expect current GitHub CLI minor line**
  - Update `tests/test_image.py` `EXPECTED_VERSIONS["gh"]` to `2.89.` to match the CLI shipped in the image

### Removed

- **PR Title Check GitHub Actions workflow** ([#444](https://github.com/vig-os/devcontainer/issues/444))
  - Remove `.github/workflows/pr-title-check.yml`; commit message rules remain enforced via local hooks and `validate-commit-msg`
  - Remove `--subject-only` from `validate-commit-msg` (it existed only for PR title CI)

### Fixed

- **Smoke-test deploy restores workspace CHANGELOG for prepare-release** ([#417](https://github.com/vig-os/devcontainer/issues/417))
  - Add `prepare-changelog unprepare` to rename the top `## [semver] - …` heading to `## Unreleased`
  - `init-workspace.sh --smoke-test` copies `.devcontainer/CHANGELOG.md` into workspace `CHANGELOG.md` and runs unprepare; remove duplicate remap from smoke-test dispatch workflow
- **Release app permission docs now include downstream workflow dispatch requirements** ([#397](https://github.com/vig-os/devcontainer/issues/397))
  - Update `docs/RELEASE_CYCLE.md` to require `Actions` read/write for `RELEASE_APP` on the validation repository
  - Clarify this is required so downstream `repository-dispatch.yml` can trigger release orchestration workflows via `workflow_dispatch`
- **Smoke-test dispatch no longer fails on release PR self-approval** ([#402](https://github.com/vig-os/devcontainer/issues/402))
  - Remove bot self-approval from `repository-dispatch.yml` and replace with release-kind labeling plus auto-merge enablement
  - Remove in-job polling for release PR merge and downstream release execution from phase 1 orchestration
  - Phase 2 (`on-release-pr-merge.yml`) fails validation unless the merged release PR has `release-kind:final` or `release-kind:candidate`
- **Sync-main-to-dev PRs now trigger CI reliably in downstream repos** ([#398](https://github.com/vig-os/devcontainer/issues/398))
  - Replace API-based sync branch creation with `git push` in `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- **Sync-main-to-dev no longer dispatches CI via workflow_dispatch** ([#405](https://github.com/vig-os/devcontainer/issues/405))
  - `workflow_dispatch` runs are omitted from the PR status check rollup, so they do not satisfy branch protection on the sync PR
  - Remove the post-PR `gh workflow run ci.yml` step and drop `actions: write` from the sync job in `.github/workflows/sync-main-to-dev.yml` and `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- **Sync-main-to-dev conflict detection uses merge-tree** ([#410](https://github.com/vig-os/devcontainer/issues/410))
  - Replace working-tree trial merge with `git merge-tree --write-tree` so clean merges are not mislabeled as conflicts
  - Enable auto-merge when dev merges cleanly with main; print merge-tree output on conflicts; fail the step on unexpected errors
- **Smoke-test release phase 2 branch-not-found failure** ([#419](https://github.com/vig-os/devcontainer/issues/419))
  - Merge phase 2 (`on-release-pr-merge.yml`) back into `repository-dispatch.yml` so the release runs while `release/<version>` still exists, matching the normal release flow
  - Remove `on-release-pr-merge.yml` from the smoke-test template
- **Pinned commit-action to v0.2.0** ([#354](https://github.com/vig-os/devcontainer/issues/354))
  - Updated workflow pins from `vig-os/commit-action@c0024cb` (v0.1.5) to `1bc004353d08d9332a0cb54920b148256220c8e0` (v0.2.0) in release, sync-issues, prepare-release, and smoke-test workflows
  - Upstream v0.2.0 adds bounded retry with exponential backoff for transient GitHub API failures (configurable `MAX_ATTEMPTS` and delay bounds)
  - Efficient multi-file commits via `createTree` inline content for text files, binary blobs only when needed, and chunked tree creation for large change sets
  - Exports `isBinaryFile`, `getFileMode`, and `TREE_ENTRY_CHUNK_SIZE` for library use; sequential binary blob creation to reduce secondary rate-limit bursts

- **Release finalization now commits generated docs and refreshes PR content** ([#300](https://github.com/vig-os/devcontainer/issues/300))
  - Final release automation regenerates docs before committing so pre-commit `generate-docs` does not fail CI with tracked file diffs
  - Release PR body is refreshed from finalized `CHANGELOG.md`
- **Release attestation warnings reduced by granting artifact metadata permission** ([#348](https://github.com/vig-os/devcontainer/issues/348))
  - Add `artifact-metadata: write` to the release publish job so attestation steps can persist metadata storage records
  - Keep `actions/attest`-based SBOM attestation path and remove missing-permission warnings from publish runs
- **Smoke-test dispatch deploy now repairs workspace ownership before changelog copy** ([#352](https://github.com/vig-os/devcontainer/issues/352))
  - Add a write probe and conditional `sudo chown -R` in `assets/smoke-test/.github/workflows/repository-dispatch.yml` after installer execution
  - Prevent `Permission denied` failures when copying `.devcontainer/CHANGELOG.md` to repository root in GitHub-hosted runner jobs
- **Smoke-test release lookup no longer treats missing tags as existing releases** ([#355](https://github.com/vig-os/devcontainer/issues/355))
  - Change `assets/smoke-test/.github/workflows/repository-dispatch.yml` to branch on `gh api` exit status when querying `releases/tags/<tag>`
  - Ensure missing release tags follow the create path instead of failing with `prerelease=null` mismatch
- **Bounded retry added for network-dependent setup and prepare-release calls** ([#357](https://github.com/vig-os/devcontainer/issues/357))
  - Replace shell-based retry helper with pure Python `retry` CLI in `vig-utils` (`packages/vig-utils/src/vig_utils/retry.py`)
  - Update this repository CI workflows to call `uv run retry` after `setup-env` dependency sync
  - Update downstream workflow templates to call `retry` directly in devcontainer jobs and remove `source` lines
  - Ensure downstream containerized jobs resolve image tags from `.vig-os` instead of hardcoded `latest`
  - Bundle idempotency guards for branch/PR/tag/release creation paths to keep retried network calls safe on reruns
  - Remove synced `retry.sh` artifacts and BATS retry tests in favor of `vig-utils` pytest coverage
- **Release workflow no longer fails when retry tooling is unavailable** ([#365](https://github.com/vig-os/devcontainer/issues/365))
  - Extend `.github/actions/setup-env/action.yml` with a reusable `retry` shell function exported via `BASH_ENV` as the retry single source of truth
  - Add `setup-env` input support for uv-only usage by allowing Python setup to be disabled when jobs only need retry tooling
  - Switch release workflow retry calls from `uv run retry` to shared `retry` and remove duplicated inline retry implementations
- **Upstream sync workflows no longer depend on pre-published GHCR image tags** ([#367](https://github.com/vig-os/devcontainer/issues/367))
  - Remove upstream `.vig-os` files at repository root and `assets/smoke-test/` to eliminate downstream-only configuration from upstream CI
  - Refactor `.github/workflows/sync-issues.yml` and `.github/workflows/sync-main-to-dev.yml` to run natively on runners via `./.github/actions/setup-env` instead of `resolve-image` + `container`
- **Release test-image setup now recovers from uv sync crashes** ([#370](https://github.com/vig-os/devcontainer/issues/370))
  - Harden `.github/actions/setup-env/action.yml` to retry `uv sync --frozen --all-extras` once after clearing uv cache and removing stale `.venv`
  - Prevent repeat release test failures when `setup-env` is executed multiple times in the same job
- **Release setup-env no longer self-sources retry helper via BASH_ENV** ([#374](https://github.com/vig-os/devcontainer/issues/374))
  - Guard the retry-helper merge logic in `.github/actions/setup-env/action.yml` to skip merging when `PREV_BASH_ENV` already equals `RETRY_HELPER`
  - Prevent infinite `source` recursion and exit 139 crashes when `setup-env` is invoked multiple times in one job
- **Smoke-test dispatch now checks out repository before local setup action** ([#376](https://github.com/vig-os/devcontainer/issues/376))
  - Add `actions/checkout` to the `smoke-test` job in `.github/workflows/release.yml` before invoking `./.github/actions/setup-env`
  - Prevent dispatch failures caused by missing local action metadata (`action.yml`) in a fresh job workspace
- **Workspace resolve-image jobs now checkout local action metadata** ([#380](https://github.com/vig-os/devcontainer/issues/380))
  - Update `sparse-checkout` in workspace `resolve-image` jobs to include `.github/actions/resolve-image` in addition to `.vig-os`
  - Prevent CI failures in downstream deploy PRs where local composite actions were missing from sparse checkout
- **Smoke-test dispatch gh jobs now set explicit repo context** ([#386](https://github.com/vig-os/devcontainer/issues/386))
  - Add job-level `GH_REPO: ${{ github.repository }}` to `cleanup-release`, `trigger-prepare-release`, `ready-release-pr`, and `trigger-release` in `assets/smoke-test/.github/workflows/repository-dispatch.yml`
  - Prevent `gh` CLI failures (`fatal: not a git repository`) in runner jobs that do not perform `actions/checkout`
- **Smoke-test release orchestration now validates workflow contract before dispatch** ([#389](https://github.com/vig-os/devcontainer/issues/389))
  - Add a preflight check that verifies `prepare-release.yml` and `release.yml` are resolvable on dispatch ref `dev` before downstream orchestration starts
  - Dispatch and polling now use explicit ref/branch context (`--ref dev` / `--branch dev`) to avoid default-branch workflow registry drift and `404 workflow not found` failures
- **Smoke-test preflight now uses gh CLI ref-compatible workflow validation** ([#392](https://github.com/vig-os/devcontainer/issues/392))
  - Update `assets/smoke-test/.github/workflows/repository-dispatch.yml` preflight checks to call `gh workflow view` with `--yaml` when `--ref` is set
  - Prevent false preflight failures caused by newer GitHub CLI argument validation before `prepare-release` dispatch
- **Downstream release workflow templates hardened for smoke-test orchestration** ([#394](https://github.com/vig-os/devcontainer/issues/394))
  - Add missing `git config --global --add safe.directory "$GITHUB_WORKSPACE"` in containerized release and sync jobs that run git after checkout
  - Decouple `release.yml` rollback container startup from `needs.core.outputs.image_tag` by resolving the image in a dedicated `resolve-image` job
  - Add explicit release caller/reusable workflow permissions for `actions` and `pull-requests` operations, and update dispatch header comments to reference only current CI workflows
- **Workspace containerized workflows now pin bash for run steps** ([#395](https://github.com/vig-os/devcontainer/issues/395))
  - Set `defaults.run.shell: bash` in containerized workspace release and prepare jobs so `set -euo pipefail` scripts do not execute under POSIX `sh`
  - Prevent downstream smoke-test failures caused by `set: Illegal option -o pipefail` in container jobs
- **Downstream release templates now require explicit app tokens for write paths** ([#400](https://github.com/vig-os/devcontainer/issues/400))
  - Update `assets/workspace/.github/workflows/prepare-release.yml`, `release-core.yml`, `release-publish.yml`, `release.yml`, and `sync-issues.yml` to remove `github.token` fallback from protected write operations
  - Route protected branch/ref writes through Commit App tokens and release orchestration/issue operations through Release App tokens
  - Document downstream token requirements in `docs/DOWNSTREAM_RELEASE.md` and `docs/CROSS_REPO_RELEASE_GATE.md`
  - Use `github.token` specifically for Actions cache deletion in `sync-issues.yml` because that API path requires explicit `actions: write` job token scope
  - Use Commit App credentials for rollback checkout in `release.yml` so rollback branch/tag writes can still bypass protected refs
- **setup-env retries uv install on transient GitHub Releases download failures** ([#407](https://github.com/vig-os/devcontainer/issues/407))
  - Add `continue-on-error` plus a delayed second attempt for `astral-sh/setup-uv` in `.github/actions/setup-env/action.yml`
  - Reduce flaky release publish failures when GitHub CDN returns transient HTTP errors for uv release assets
- **Smoke-test deploy keeps workspace scaffold as root CHANGELOG** ([#403](https://github.com/vig-os/devcontainer/issues/403))
  - Stop overwriting `CHANGELOG.md` with a minimal stub in `assets/smoke-test/.github/workflows/repository-dispatch.yml`
  - Require the workspace `CHANGELOG.md` from `init-workspace` so downstream `prepare-release` validation matches shipped layout
  - When the first changelog section is `## [X.Y.Z] - …` (TBD or a release date), remap that top version header to `## Unreleased` so downstream `prepare-release` can run
- **Smoke-test dispatch release validate no longer runs docker inside devcontainer** ([#421](https://github.com/vig-os/devcontainer/issues/421))
  - Remove redundant `docker manifest inspect` step from `release-core.yml` validate job (container image is already proof of accessibility; `resolve-image` validates on the runner)
  - Set `GH_REPO` for rollback `gh issue create` in workspace `release.yml` when git checkout is skipped
- **Container image tests expect current uv minor line** ([#423](https://github.com/vig-os/devcontainer/issues/423))
  - Update `tests/test_image.py` `EXPECTED_VERSIONS["uv"]` to match uv 0.11.x from the latest release install path in the image build
- **Container image tests expect current just minor line** ([#423](https://github.com/vig-os/devcontainer/issues/423))
  - Update `tests/test_image.py` `EXPECTED_VERSIONS["just"]` to match just 1.48.x from the latest release install path in the image build
- **Smoke-test dispatch approves release PR before downstream release** ([#430](https://github.com/vig-os/devcontainer/issues/430))
  - Grant `pull-requests: write` on `ready-release-pr` and approve with `github.token` (`github-actions[bot]`)
  - Satisfy `release-core.yml` approval gate without the release app self-approving its own PR
- **commit-action retries enabled for transient git ref API failures** ([#436](https://github.com/vig-os/devcontainer/issues/436))
  - Set `MAX_ATTEMPTS: "3"` on every `vig-os/commit-action` step so v0.2.0 bounded retry actually runs (default was 1)
  - Covers smoke-test deploy, prepare-release, release finalization, sync-issues, and workspace templates
- **Release validation fails when bot approves PR** ([#438](https://github.com/vig-os/devcontainer/issues/438))
  - Add fallback to individual PR review check when `reviewDecision` is empty (bot approvals not counted by branch protection)
- **Downstream candidate RC tag can match upstream dispatch** ([#441](https://github.com/vig-os/devcontainer/issues/441))
  - Workspace `release.yml` / `release-core.yml` accept optional `rc-number` so candidate tags are not always recomputed from local tags only
  - Smoke-test `repository-dispatch.yml` exposes `base_version` and `rc_number` job outputs for orchestration that calls workspace `release.yml`
- **Release validate fails early when GitHub Release already exists** ([#443](https://github.com/vig-os/devcontainer/issues/443))
  - Validate job in `.github/workflows/release.yml` queries `GET /repos/.../releases/tags/<PUBLISH_VERSION>` with retries and classifies errors like the downstream RC gate; only a documented not-found response is treated as “no release,” and ambiguous API failures fail closed before build/sign/publish
  - Publish job uses the same existence checks before and after `gh release create` instead of `gh release view` with discarded stderr
- **Release tag resolution and GitHub Release view retries** ([#446](https://github.com/vig-os/devcontainer/issues/446))
  - Fall back to plain `refs/tags/<tag>` when the peeled ref is empty (lightweight remote tags) in `.github/workflows/release.yml`, `release-core.yml`, and `release-publish.yml`
  - Use one retried `gh release view` in workspace `release-publish.yml` so draft/prerelease skip paths parse JSON from the same successful response
- **Workspace release publish `tag_already_exists` input coercion** ([#451](https://github.com/vig-os/devcontainer/issues/451))
  - Pass a boolean into `release-publish.yml` via `needs.core.outputs.tag_already_exists == 'true'` so `workflow_call` does not reject string `"true"`/`"false"` job outputs

### Security

- **Smoke-test dispatch workflow permissions now follow least privilege** ([#340](https://github.com/vig-os/devcontainer/issues/340))
  - Reduce `assets/smoke-test/.github/workflows/repository-dispatch.yml` workflow token permissions from write to read by default
  - Grant `contents: write` only to `publish-release`, the single job that creates or edits GitHub Releases

## [0.3.0](https://github.com/vig-os/devcontainer/releases/tag/0.3.0) - 2026-03-13

### Added

- **Image tools** ([#212](https://github.com/vig-os/devcontainer/issues/212))
  - Install rsync
- **Preserve user-authored files during `--force` workspace upgrades** ([#212](https://github.com/vig-os/devcontainer/issues/212))
  - `init-workspace --force` no longer overwrites `README.md`, `CHANGELOG.md`, `LICENSE`, `.github/CODEOWNERS`, or `justfile.project`
- **Devcontainer and git recipes in justfile.base** ([#71](https://github.com/vig-os/devcontainer/issues/71))
  - Devcontainer group (host-side only): `up`, `down`, `status`, `logs`, `shell`, `restart`, `open`
  - Auto-detect podman/docker compose; graceful failure if run inside container
  - Git group: `log` (pretty one-line, last 20), `branch` (current + recent)
- **CI status column in just gh-issues PR table** ([#143](https://github.com/vig-os/devcontainer/issues/143))
  - PR table shows CI column with pass/fail/pending summary (✓ 6/6, ⏳ 3/6, ✗ 5/6)
  - Failed check names visible when checks fail
  - CI cell links to GitHub PR checks page
- **Config-driven model tier assignments for agent skills** ([#103](https://github.com/vig-os/devcontainer/issues/103))
  - Extended `.cursor/agent-models.toml` with `standard` tier (sonnet-4.5) and `[skill-tiers]` mapping for skill categories (data-gathering, formatting, review, orchestration)
  - New rule `.cursor/rules/subagent-delegation.mdc` documenting when and how to delegate mechanical sub-steps to lightweight subagents via the Task tool
  - Added `## Delegation` sections to 12 skills identifying steps that should spawn lightweight/standard-tier subagents to reduce token consumption on the primary autonomous model
  - Skills updated: `worktree_solve-and-pr`, `worktree_brainstorm`, `worktree_plan`, `worktree_execute`, `worktree_verify`, `worktree_pr`, `worktree_ci-check`, `worktree_ci-fix`, `code_review`, `issue_triage`, `pr_post-merge`, `ci_check`
- **hadolint pre-commit hook for Containerfile linting** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Add `hadolint` hook to `.pre-commit-config.yaml`, pinned by SHA (v2.9.3)
  - Enforce Dockerfile best practices: pinned base image tags, consolidated `RUN` layers, shellcheck for inline scripts
  - Fix `tests/fixtures/sidecar.Containerfile` to pass hadolint with no warnings
- **tmux installed in container image for worktree session persistence** ([#130](https://github.com/vig-os/devcontainer/issues/130))
  - Add `tmux` to the Containerfile `apt-get install` block
  - Enables autonomous worktree agents to survive Cursor session disconnects
- **pr_solve skill — diagnose PR failures, plan fixes, execute** ([#133](https://github.com/vig-os/devcontainer/issues/133))
  - Single entry point that gathers CI failures, review feedback, and merge state into a consolidated diagnosis
  - Presents diagnosis for approval before any fixes, plans fixes using design_plan conventions, executes with TDD discipline
  - Pre-commit hook `check-skill-names` enforces `[a-z0-9][a-z0-9_-]*` naming for skill directories
  - BATS test suite with canary test that injects a bad name into the real repo
  - TDD scenario checklist expanded with canary, idempotency, and concurrency categories
- **Optional reviewer parameter for autonomous worktree pipeline** ([#102](https://github.com/vig-os/devcontainer/issues/102))
  - Support `reviewer` parameter in `just worktree-start`
  - Propagate `PR_REVIEWER` via tmux environment to the autonomous agent
  - Update `worktree_pr` skill to automatically request review when `PR_REVIEWER` is set
- **Inception skill family for pre-development product thinking** ([#90](https://github.com/vig-os/devcontainer/issues/90))
  - Four-phase pipeline: `inception_explore` (divergent problem understanding), `inception_scope` (convergent scoping), `inception_architect` (pattern-validated design), `inception_plan` (decomposition into GitHub issues)
  - Document templates: `docs/templates/RFC.md` (Problem Statement, Proposed Solution, Alternatives, Impact, Phasing) and `docs/templates/DESIGN.md` (Architecture, Components, Data Flow, Technology Stack, Testing)
  - Document directories: `docs/rfcs/` and `docs/designs/` for durable artifacts
  - Certified architecture reference repos embedded in `inception_architect` skill: ByteByteGoHq/system-design-101, donnemartin/system-design-primer, karanpratapsingh/system-design, binhnguyennus/awesome-scalability, mehdihadeli/awesome-software-architecture
  - Fills the gap between "I have an idea" and "I have issues ready for design"
- **Automatic update notifications on devcontainer attach** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Wire `version-check.sh` into `post-attach.sh` for automatic update checks
  - Silent, throttled checks (24-hour interval by default)
  - Graceful failure - never disrupts the attach process
- **Host-side devcontainer upgrade recipe** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - New `just devcontainer-upgrade` recipe for convenient upgrades from host
  - Container detection - prevents accidental execution inside devcontainer
  - Clear error messages with instructions when run from wrong context
- **`just check` recipe for version management** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Expose version-check.sh subcommands: `just check`, `just check config`, `just check on/off`, `just check 7d`
  - User-friendly interface for managing update notifications
- **Cursor worktree support for parallel agent development** ([#64](https://github.com/vig-os/devcontainer/issues/64))
  - `.cursor/worktrees.json` for native Cursor worktree initialization (macOS/Linux local)
  - `justfile.worktree` with tmux + cursor-agent CLI recipes (`worktree-start`, `worktree-list`, `worktree-attach`, `worktree-stop`, `worktree-clean`) for devcontainer environments
  - Autonomous worktree skills: `worktree_brainstorm`, `worktree_plan`, `worktree_execute`, `worktree_verify`, `worktree_pr`, `worktree_ask`, `worktree_solve-and-pr`
  - Sync manifest updated to propagate worktree config and recipes to downstream projects
- **GitHub issue and PR dashboard recipe** ([#84](https://github.com/vig-os/devcontainer/issues/84))
  - `just gh-issues` displays open issues grouped by milestone in rich tables with columns for type, title, assignee, linked branch, priority, scope, effort, and semver
  - Open pull requests section with author, branch, review status, and diff delta
  - Linked branches fetched via a single GraphQL call
  - Ships to downstream workspaces via sync manifest (`.devcontainer/justfile.gh` + `.devcontainer/scripts/gh_issues.py`)
- **Issue triage agent skill** ([#81](https://github.com/vig-os/devcontainer/issues/81))
  - Cursor skill at `.cursor/skills/issue_triage/` for triaging open issues across priority, area, effort, SemVer impact, dependencies, and release readiness
  - Decision matrix groups issues into parent/sub-issue clusters with milestone suggestions
  - Predefined label taxonomy (`label-taxonomy.md`) for priority, area, effort, and SemVer dimensions
  - Sync manifest updated to propagate skill to workspace template
- **Cursor commands and rules for agent-driven development workflows** ([#63](https://github.com/vig-os/devcontainer/issues/63))
  - Always-on rules: `coding-principles.mdc` (YAGNI, minimal diff, DRY, no secrets, traceability, single responsibility) and `tdd.mdc` (RED-GREEN-REFACTOR discipline)
  - Tier 1 commands: `start-issue.md`, `create-issue.md`, `brainstorm.md`, `tdd.md`, `review.md`, `verify.md`
  - Tier 2 commands: `check-ci.md`, `fix-ci.md`
  - Tier 3 commands: `plan.md`, `execute-plan.md`, `debug.md`
- **Agent-friendly issue templates, changelog rule, and PR template enhancements** ([#61](https://github.com/vig-os/devcontainer/issues/61))
  - Cursor rule `.cursor/rules/changelog.mdc` (always applied) guiding agents on when, where, and how to update CHANGELOG.md
  - Changelog Category dropdown added to `bug_report.yml`, `feature_request.yml`, and `task.yml` issue templates
  - New issue templates: `refactor.yml` (scope/invariants), `documentation.yml` (docs/templates workflow), `ci_build.yml` (target workflows/triggers/release impact)
  - Template chooser `config.yml` disabling blank issues and linking to project docs
  - PR template enhanced with explicit Changelog Entry section, CI/Build change type, and updated checklist referencing `docs/templates/` and `just docs`
- **GitHub issue and PR templates in workspace template** ([#63](https://github.com/vig-os/devcontainer/issues/63))
  - Pull request template, issue templates, Dependabot config, and `.gitmessage` synced to `assets/workspace/`
  - Ground truth lives in repo root; `assets/workspace/` is generated output
- **cursor-agent CLI pre-installed in devcontainer image** ([#108](https://github.com/vig-os/devcontainer/issues/108))
  - Enables `just worktree-start` to work out of the box without manual installation
- **Automatic merge commit message compliance** ([#79](https://github.com/vig-os/devcontainer/issues/79))
  - `setup-gh-repo.sh` configures repo merge settings via `gh api` (`merge_commit_title=PR_TITLE`, `merge_commit_message=PR_BODY`, `allow_auto_merge=true`)
  - Wired into `post-create.sh` so downstream devcontainer projects get compliant merge commits automatically
  - `--subject-only` flag for `validate-commit-msg` to validate PR titles without requiring body or Refs
  - `pr-title-check.yml` CI workflow enforces commit message standard on PR titles
  - PR body template includes `Refs: #` placeholder for merge commit traceability
- **Smoke-test repo bootstrap validation** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Downstream smoke coverage that bootstraps a workspace from the template and verifies `ci.yml` passes on a real GitHub-hosted runner
- **`bandit` pre-installed in devcontainer image** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - `bandit[toml]` added to the system Python install in the Containerfile
- **`pre-commit` pre-installed in CI `setup-env` action** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Workspace `setup-env` composite action now installs `pre-commit` as a mandatory step so hooks are available in bare-runner CI without a devcontainer
- **`setup-gh-repo.sh` detaches org default code security configuration** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - On post-create, detach any org-level default security config from the repo to avoid conflicts with the security workflows shipped in the workspace template
  - Graceful fallback when repo ID cannot be resolved or permissions are insufficient
- **`init-workspace.sh` runs `just sync` after placeholder replacement** ([#170](https://github.com/vig-os/devcontainer/issues/170))
  - Resolves the `uv.lock` for the new project name and installs the project package into the venv during workspace bootstrap
- **Candidate publishing mode in release workflow** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `release.yml` now supports `release-kind=candidate` (default) and infers the next available `X.Y.Z-rcN` tag automatically
  - Candidate runs create and push Git tags, publish candidate manifests, and keep candidate tags after final release
  - Final runs remain available via `release-kind=final` and are exposed by `just finalize-release`
- **PR-based dev sync after release** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `sync-main-to-dev.yml` replaces `post-release.yml` — syncs main into dev via PR instead of direct push, satisfying branch protection rules
  - Detects merge conflicts, labels `merge-conflict` with resolution instructions
  - Auto-merge enabled for conflict-free PRs; stale sync branches cleaned up automatically
- **hadolint installed and wired into CI tooling** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Install `hadolint` in the devcontainer image with SHA-256 checksum verification
  - Add image test coverage to verify `hadolint` is available in the built image
  - Configure pre-commit to use the local `hadolint` binary and install it in `setup-env`/`test-project` workflows
- **Taplo TOML linting in pre-commit** ([#181](https://github.com/vig-os/devcontainer/issues/181))
  - Add SHA-pinned `taplo-format` and `taplo-lint` hooks to enforce TOML formatting and schema-aware validation
  - Add `.taplo.toml` configuration (local to this repository, not synced downstream)
- **Add `--smoke-test` flag to deploy smoke-test-specific assets** ([#250](https://github.com/vig-os/devcontainer/issues/250))
  - `init-workspace.sh --smoke-test` deploys files from `assets/smoke-test/` (currently `repository-dispatch.yml` and `README.md`)
  - `install.sh` forwards `--smoke-test` flag to `init-workspace.sh`
  - Smoke mode implies `--force --no-prompts` for unattended use
  - Refactor `initialized_workspace` fixture into reusable `_init_workspace()` with `smoke_test` parameter
- **Root `.vig-os` config file as devcontainer version SSoT** ([#257](https://github.com/vig-os/devcontainer/issues/257))
  - Add committed `assets/workspace/.vig-os` key/value config with `DEVCONTAINER_VERSION` as the canonical version source
  - Update `docker-compose.yml`, `initialize.sh`, and `version-check.sh` to consume `.vig-os`-driven version flow
  - Extend integration/image tests for `.vig-os` presence and graceful handling when `.vig-os` is missing
- **VS Code settings synced via manifest**
  - Added `.vscode/settings.json` to `scripts/manifest.toml` to keep editor settings consistent across root repo and workspace template
- **Cross-repo smoke-test dispatch on RC publish** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - RC candidate publishes now trigger `repository_dispatch` in `vig-os/devcontainer-smoke-test` with the RC tag payload
  - Release process now includes a documented manual smoke gate before running final publish
- **Automated RC deploy-and-test via PR in smoke-test repo** ([#258](https://github.com/vig-os/devcontainer/issues/258))
  - Dispatch workflow now deploys the tag, creates a signed commit on `chore/deploy-<tag>`, and opens a PR to `dev`
  - CI workflows (`ci.yml`, `ci-container.yml`) trigger on the deploy PR, and auto-merge is enabled when checks pass
  - Stale deploy PRs are closed before each new deployment
  - The smoke-test repo keeps audit trail through deploy PRs and merge history instead of a local changelog
  - Dispatch payload tag validation now enforces semver format `X.Y.Z` or `X.Y.Z-rcN` before using the tag in refs/URLs
  - CI security scan now includes a time-bounded exception for `CVE-2026-31812` in `uv`/`uvx` pending upstream dependency patch release

### Changed

- **Release CHANGELOG flow redesigned** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - `prepare-release.yml` now freezes CHANGELOG on dev (Unreleased → [X.Y.Z] - TBD + fresh empty Unreleased), then forks release branch and strips the empty Unreleased section
  - Dev never enters a state without `## Unreleased`; both branches share the [X.Y.Z] section for clean merges
  - Candidate releases skip CHANGELOG changes; only final releases set the date
  - No CHANGELOG reset needed during post-release sync
- **Release automation now uses dedicated GitHub App identities** ([#172](https://github.com/vig-os/devcontainer/issues/172))
  - Replaced deprecated `APP_SYNC_ISSUES_*` secrets with `RELEASE_APP_*` for release and preparation workflows
  - `sync-issues.yml` now uses `COMMIT_APP_*`; `sync-main-to-dev.yml` uses both apps (commit app for refs, release app for PR operations)
  - Removed automatic `sync-issues` trigger from `sync-main-to-dev.yml` and documented the app permission model in `docs/RELEASE_CYCLE.md`
- **Container CI defaults image tag from `.vig-os`** ([#264](https://github.com/vig-os/devcontainer/issues/264))
  - `ci.yml` and `ci-container.yml` now run only on `pull_request` and `workflow_dispatch` after removing unused `workflow_call` triggers
  - `ci-container.yml` now resolves `DEVCONTAINER_VERSION` from `.vig-os` before container jobs start
  - Manual `workflow_dispatch` runs can still override the image via `image-tag`; fallback remains `latest` when no version is available
  - Added an early manifest check in `resolve-image` so workflows fail fast if the resolved image tag is unavailable or inaccessible

- **worktree-clean: add filter mode for stopped-only vs all** ([#158](https://github.com/vig-os/devcontainer/issues/158))
  - Default `just worktree-clean` (no args) now cleans only stopped worktrees, skips running tmux sessions
  - `just worktree-clean all` retains previous behavior (clean all worktrees) with warning
  - Summary output shows cleaned vs skipped worktrees
  - `just wt-clean` alias unchanged
- **Consolidate sync_manifest.py and utils.py into manifest-as-config architecture** ([#89](https://github.com/vig-os/devcontainer/issues/89))
  - Extract transform classes (Sed, RemoveLines, etc.) to `scripts/transforms.py`
  - Unify sed logic: `substitute_in_file()` in utils shared by sed_inplace and Sed transform
  - Convert MANIFEST from Python code to declarative `scripts/manifest.toml`
- **justfile.base is canonical at repo root, synced via manifest** ([#71](https://github.com/vig-os/devcontainer/issues/71))
  - Root `justfile.base` is now the single source of truth; synced to `assets/workspace/.devcontainer/justfile.base` via `sync_manifest.py`
  - `just sync-workspace` and prepare-build keep workspace template in sync
- **Autonomous PR skills use pull request template** ([#147](https://github.com/vig-os/devcontainer/issues/147))
  - `pr_create` and `worktree_pr` now read `.github/pull_request_template.md` and fill each section from available context
  - Explicit read-then-fill procedure with section-by-section mapping (Description, Type of Change, Changelog Entry, Testing, Checklist, Refs)
  - Ensures autonomous PRs match manual PR structure and include all checklist items
- **Rename skill namespace separator from colon to underscore** ([#128](https://github.com/vig-os/devcontainer/issues/128))
  - All skill directories under `.cursor/skills/` and `assets/workspace/.cursor/skills/` renamed (e.g. `issue:create` → `issue_create`)
  - All internal cross-references, frontmatter, prose, `CLAUDE.md` command table, and label taxonomy updated
  - `issue_create` skill enhanced: gathers context via `just gh-issues` before drafting, suggests parent/child relationships and milestones
  - `issue_create` skill now includes TDD acceptance criterion for testable issue types
  - Remaining `sync-issues` workflow trigger references removed from skills
  - `tdd.mdc` expanded with test scenario checklist and test type guidance; switched from always-on to glob-triggered on source/test files
  - `code_tdd`, `code_execute`, and `worktree_execute` skills now reference `tdd.mdc` explicitly
- **Clickable issue and PR numbers in gh-issues table** ([#104](https://github.com/vig-os/devcontainer/issues/104))
  - `#` column in issue and PR tables now uses Rich OSC 8 hyperlinks to GitHub URLs
  - Clicking an issue or PR number opens it in the browser (or Cursor's integrated terminal)
- **PR template aligned with canonical commit types** ([#115](https://github.com/vig-os/devcontainer/issues/115))
  - Replace ad-hoc Type of Change checkboxes with the 10 canonical commit types
  - Move breaking change from type to a separate modifier checkbox
  - Add release-branch hint to Related Issues section
- **Updated update notification message** ([#73](https://github.com/vig-os/devcontainer/issues/73))
  - Fixed misleading `just update` instruction (Python deps, not devcontainer upgrade)
  - Show correct upgrade instructions: `just devcontainer-upgrade` and curl fallback
  - Clarify that upgrade must run from host terminal, not inside container
  - Add reminder to rebuild container in VS Code after upgrade
- **Declarative Python sync manifest** ([#67](https://github.com/vig-os/devcontainer/issues/67))
  - Replaced `sync-manifest.txt` + bash function and `sync-workspace.sh` with `scripts/sync_manifest.py`
  - Single source of truth for which files to sync and what transformations to apply
  - `prepare-build.sh` and `just sync-workspace` both call the same manifest
- **Namespace-prefixed Cursor skill names** ([#67](https://github.com/vig-os/devcontainer/issues/67))
  - Renamed all 15 skills with colon-separated namespace prefixes (`issue:`, `design:`, `code:`, `git:`, `ci:`, `pr:`)
  - Enables filtering by namespace when invoking skills (e.g., typing `code:` shows implementation skills)
- **`--org` flag for install script** ([#33](https://github.com/vig-os/devcontainer/issues/33))
  - Allows overriding the default organization name (default: `vigOS`)
  - Passes `ORG_NAME` as environment variable to the container
  - Usage: `curl -sSf ... | bash -s --org MyOrg -- ~/my-project`
  - Unit tests for `--org` flag in help, default value, and custom override
- **Virtual environment prompt renaming** ([#34](https://github.com/vig-os/devcontainer/issues/34))
  - Post-create script updates venv prompt from "template-project" to project short name
  - Integration test verifies venv activate script does not contain "template-project"
- **BATS (Bash Automated Testing System) shell testing framework** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - npm dependencies for bats, bats-support, bats-assert, and bats-file
  - `test-bats` justfile task and requirements configuration
  - `test_helper.bash` supporting both local (node_modules) and CI (BATS_LIB_PATH) library resolution
  - CI integration in setup-env and test-project actions with conditional parallel execution via GNU parallel
  - Comprehensive BATS test suites for build, clean, init, install, and prepare-build scripts
  - Tests verify script structure, argument parsing, function definitions, error handling, and OS/runtime detection patterns
- **Post-install user configuration step** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Automatically call copy-host-user-conf.sh after workspace initialization
  - `run_user_conf()` helper for host-side setup (git, ssh, gh)
  - Integration tests for .devcontainer/.conf/ directory creation and expected config files
- **Git repository initialization in install script** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - `setup_git_repo()` function to initialize git if missing
  - Creates initial commit "chore: initial project scaffold" for new repos
  - Automatically creates main and dev branches
  - `test-install` justfile recipe for running install tests
  - Integration tests for git repo initialization, branches, and initial commit
- **Commit message standardization** ([#36](https://github.com/vig-os/devcontainer/issues/36))
  - Commit message format: `type(scope)!: subject` with mandatory `Refs: #<issue>` line
  - Documentation: `docs/COMMIT_MESSAGE_STANDARD.md` defining format, approved types (feat, fix, docs, chore, refactor, test, ci, build, revert, style), and traceability requirements
  - Validation script: `scripts/validate_commit_msg.py` enforcing the standard
  - Commit-msg hook: `.githooks/commit-msg` runs validation on every commit
  - Pre-commit integration: commit-msg stage hook in `.pre-commit-config.yaml`
  - Git commit template: `.gitmessage` with format placeholder
  - Cursor integration: `.cursor/rules/commit-messages.mdc` and `.cursor/commands/commit-msg.md` for AI-assisted commit messages
  - Workspace template: all commit message tooling included in `assets/workspace/` for new projects
  - Tests: `tests/test_validate_commit_msg.py` with comprehensive validation test cases
- **nano text editor** in devcontainer image ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Chore Refs exemption** in commit message standard ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - `chore` commits may omit the `Refs:` line when no issue or PR is directly related
  - Validator updated with `REFS_OPTIONAL_TYPES` to accept chore commits without Refs
- **Dependency review allowlist entry** for debug@0.6.0 ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Added GHSA-9vvw-cc9w-f27h exception to `.github/dependency-review-allow.txt`
  - Addresses ReDoS vulnerability in transitive test dependency (bats-assert → verbose → debug)
  - High risk severity but isolated to CI/development environment with expiration 2026-11-17
|- **Dependency review exception for legacy test vulnerabilities** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Comprehensive acceptance register for 9 transitive vulnerabilities in unmaintained BATS test framework dependencies
  - All 9 vulnerabilities are isolated to CI/development environment (engine.io, debug, node-uuid, qs, tough-cookie, ws, xmlhttprequest, form-data)
  - Formal risk assessments and mitigations documented in `SECURITY.md` and `.github/dependency-review-allow.txt`
  - Expiration-enforced exceptions with 2026-11-17 expiration date to force periodic re-evaluation

- **Bandit and Safety security scanning** ([#37](https://github.com/vig-os/devcontainer/issues/37), [#50](https://github.com/vig-os/devcontainer/issues/50))
  - Bandit pre-commit hook for medium/high/critical severity Python code analysis
  - CI pipeline job with Bandit static analysis and Safety dependency vulnerability scanning
  - Reports uploaded as artifacts (30-day retention) with job summary integration
- **Scheduled weekly security scan workflow** (`security-scan.yml`) ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Full Trivy vulnerability scan (all severities) against `dev` branch every Monday 06:00 UTC
  - SBOM generation (CycloneDX) and SARIF upload to GitHub Security tab
  - Non-blocking: catches newly published CVEs between pull requests
- **Non-blocking unfixed vulnerability reporting in CI** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Additional CI scan step reports unfixed HIGH/CRITICAL CVEs for awareness without blocking the pipeline
- **Comprehensive `.trivyignore` vulnerability acceptance register** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Formal medtech-compliant register (IEC 62304 / ISO 13485) documenting 10 accepted CVEs
  - Each entry includes risk assessment, exploitability justification, fix status, and mitigation
  - 6-month expiration dates enforce periodic re-evaluation
- **Expiration-enforced dependency-review exceptions** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Allow GHSA-wvrr-2x4r-394v (bats-file false positive) via `.github/dependency-review-allow.txt`
  - CI validation step parses expiration dates and fails the pipeline when exceptions expire, forcing periodic review
- **Branch name enforcement as a pre-commit hook** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - New `branch-name` hook enforcing `<type>/<issue>-<summary>` convention (e.g. `feature/38-standardize-branching-strategy-enforcement`)
  - Pre-commit configuration updated in repo and in workspace assets (`.pre-commit-config.yaml`, `assets/workspace/.pre-commit-config.yaml`)
  - Integration tests added for valid and invalid branch names
- **Cursor rules for branch naming and issue workflow** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - `.cursor/rules/branch-naming.mdc`: topic branch naming format, branch types, workflow for creating/linking branches via `gh issue develop`
  - Guidelines for inferring branch type from issue labels and deriving short summary from issue title
- **Release cycle documentation** ([#38](https://github.com/vig-os/devcontainer/issues/38), [#48](https://github.com/vig-os/devcontainer/issues/48))
  - `docs/RELEASE_CYCLE.md` with complete release workflow, branching strategy, and CI/CD integration
  - Cursor commands: `after-pr-merge.md`, `submit-pr.md`
- **pip-licenses** installed system-wide with version verification test ([#43](https://github.com/vig-os/devcontainer/issues/43))
- **just-lsp** language server and VS Code extension for Just files ([#44](https://github.com/vig-os/devcontainer/issues/44))
- **Automated release cycle** ([#48](https://github.com/vig-os/devcontainer/issues/48))
  - `prepare-release` and `finalize-release` justfile commands triggering GitHub Actions workflows
  - `prepare-changelog.py` script with prepare, validate, reset, and finalize commands for CHANGELOG automation
  - `reset-changelog` justfile command for post-merge CHANGELOG cleanup
  - `prepare-release.yml` GitHub Actions workflow: validates semantic version, creates release branch, prepares CHANGELOG
  - Unified `release.yml` pipeline: validate → finalize → build/test → publish → rollback
  - Comprehensive test suite in `tests/test_release_cycle.py`
- **CI testing infrastructure** ([#48](https://github.com/vig-os/devcontainer/issues/48))
  - `ci.yml` workflow replacing `test.yml` with streamlined project checks (lint, changelog validation, utility and release-cycle tests)
  - Reusable composite actions: `setup-env`, `build-image`, `test-image`, `test-integration`, `test-project`
  - Artifact transfer between jobs for consistent image testing
  - Retry logic across all CI operations for transient failure handling
- **GitHub Actions SHA pinning enforcement** ([#50](https://github.com/vig-os/devcontainer/issues/50))
  - `scripts/check_action_pins.py` pre-commit hook and CI check ensuring all GitHub Actions and Docker actions reference commit SHAs
  - Comprehensive test suite in `tests/test_check_action_pins.py`
- **CODEOWNERS** for automated review assignment ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **SECURITY.md** with vulnerability reporting procedures and supported version policy ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **OpenSSF Scorecard workflow** (`scorecard.yml`) for supply chain security scoring ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **CodeQL analysis workflow** (`codeql.yml`) for automated static security analysis ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Dependabot configuration** for automated dependency update PRs with license compliance monitoring ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Vulnerability scanning and dependency review** in CI pipeline with non-blocking MEDIUM severity reporting ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **SBOM generation, container signing, and provenance attestation** in release and CI pipelines ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Edge case tests** for changelog validation, action SHA pinning, and install script ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **`vig-utils` reusable CLI utilities package** ([#51](https://github.com/vig-os/devcontainer/issues/51))
  - Python package in `packages/vig-utils/` for shared validation and build utilities
  - `validate_commit_msg` module: enforces commit message format and references standards
    - Configurable commit scopes validation: scope list can be customized per project
    - Scopes are optional by default; if used, must be in the approved list
    - Support for multiple scopes, comma-separated (e.g., `feat(api, cli): add feature`)
    - Support for GitHub auto-linked issue references (e.g., PR cross-repo links)
    - Comprehensive test suite with edge case coverage for PR and cross-repo issue links
  - `prepare_changelog` module: CHANGELOG management and validation
  - `check_action_pins` module: GitHub Actions SHA pinning enforcement
  - Integrated into CI/CD pipeline and pre-commit hooks as standard Python package
  - Package version tests verify installation and correct versioning
- **Code coverage reporting in CI** ([#52](https://github.com/vig-os/devcontainer/issues/52))
  - Code coverage measurement integrated into test action workflow
  - Coverage threshold raised to 50% for unit tests
  - Expanded unit tests to improve overall test coverage
- **File duplication detection and elimination** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Build-time manifest system detects and removes duplicated workspace assets
  - Replaces duplicated files with sync manifest entries, reducing redundancy
  - Workspace assets now synchronized from central manifest during build preparation
  - GitHub workflow templates for devcontainer projects included in sync manifest
  - Automated npm dependency management with centralized version pinning in `.github/package.json`
  - Extract build preparation into dedicated `prepare-build.sh` script with manifest sync
  - SHA-256 checksum verification tests for synced files via `parse_manifest` fixture and `test_manifest_files`
- **GitHub workflow templates for devcontainer projects** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Reusable workflow templates for continuous integration and deployment
  - Support for projects using devcontainer-based development environments
- **Centralized `@devcontainers/cli` version management** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Version pinned in `.github/package.json` for consistent behavior across workflows and builds
  - Ensures reproducibility across build and setup environments
- **`--require-scope` flag for `validate-commit-msg`** ([#58](https://github.com/vig-os/devcontainer/issues/58))
  - New CLI flag to mandate that all commits include at least one scope (e.g. `feat(api): ...`)
  - When enabled, scopeless commits (e.g. `feat: ...`) are rejected at the commit-msg stage
  - Comprehensive tests added to `test_validate_commit_msg.py`
- **`post-start.sh` devcontainer lifecycle script** ([#60](https://github.com/vig-os/devcontainer/issues/60))
  - New script runs on every container start (create + restart)
  - Handles Docker socket permissions and dependency sync via `just sync`
  - Replaces inline `postStartCommand` in `devcontainer.json`
- **Dependency sync delegated to `just sync` across all lifecycle hooks** ([#60](https://github.com/vig-os/devcontainer/issues/60))
  - `post-create.sh`, `post-start.sh`, and `post-attach.sh` now call `just sync` instead of `uv sync` directly
  - `justfile.base` `sync` recipe updated with `--all-extras --no-install-project` flags and `pyproject.toml` guard
  - Abstracts toolchain details so future dependency managers only need a recipe change

- **Git initialization default branch** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Updated git initialization to set the default branch to 'main' instead of 'master'
  - Consolidated Podman installation with other apt commands in Containerfile
- **CI release workflow uses GitHub API** ([#35](https://github.com/vig-os/devcontainer/issues/35))
  - Replace local git operations with GitHub API in prepare-release workflow
  - Use commit-action for CHANGELOG updates instead of local git
  - Replace git operations with GitHub API in release finalization flow
  - Simplify rollback and tag deletion to use gh api
  - Add sync-dependencies input to setup-env action (default: false)
  - Remove checkout step from setup-env; callers must checkout explicitly
  - Update all workflow callers to pass sync-dependencies input
  - Update CI security job to use uv with setup-env action
- **Commit message guidelines** - updated documentation ([#36](https://github.com/vig-os/devcontainer/issues/37))
- **Expected version checks** - updated ruff and pre-commit versions in test suite ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Bumped `actions/create-github-app-token`** from v1 to v2 across workflows with updated SHA pins ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Pinned `@devcontainers/cli`** to version 0.81.1 in CI for consistent behavior ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **CI and release Trivy scans gate on fixable CVEs only** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Added `ignore-unfixed: true` to blocking scan steps in `ci.yml` and `release.yml`
  - Unfixable CVEs no longer block the pipeline; documented in `.trivyignore` with risk assessments
- **Updated pre-commit hook configuration in the devcontainer** ([#38](https://github.com/vig-os/devcontainer/issues/38))
  - Exclude issue and template docs from .github_data
  - Autofix shellcheck
  - Autofix pymarkdown
  - Add license compliance check
- **Renamed `publish-container-image.yml` to `release.yml`** and expanded into unified release pipeline ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Merged `prepare-build.sh` into `build.sh`** — consolidated directory preparation, asset copying, placeholder replacement, and README updates into a single entry point ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Consolidated test files by domain** — reorganized from 6 files to 4 (`test_image.py`, `test_integration.py`, `test_utils.py`, `test_release_cycle.py`) ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Replaced `setup-python-uv` with flexible `setup-env` composite action** supporting optional inputs for podman, Node.js, and devcontainer CLI ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Reduced `sync-issues` workflow triggers** — removed `edited` event type from issues and pull_request triggers ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Release workflow pushes tested images** instead of rebuilding after tests pass ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Updated CONTRIBUTE.md** release workflow documentation to match automated process ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **CodeQL Action v3 → v4 upgrade**
  - Updated all CodeQL Action references from v3 (deprecated Dec 2026) to v4.32.2
  - Updated in `.github/workflows/codeql.yml`, `security-scan.yml`, and `ci.yml`
  - Uses commit hash `45cbd0c69e560cd9e7cd7f8c32362050c9b7ded2` for integrity
- **Sync-issues workflow output directory** ([#53](https://github.com/vig-os/devcontainer/issues/53))
  - Changed output directory from '.github_data' to 'docs' for better project structure alignment
- **Workspace `validate-commit-msg` hook configured strict-by-default** ([#58](https://github.com/vig-os/devcontainer/issues/58))
  - `assets/workspace/.pre-commit-config.yaml` now ships with explicit `args` instead of commented-out examples
  - Default args enable type enforcement, scope enforcement with `--require-scope`, and `chore` refs exemption
  - Link to `vig-utils` README added as a comment above the hook for discoverability
- **Refresh pinned Python base image digest** ([#213](https://github.com/vig-os/devcontainer/issues/213))
  - Update `python:3.12-slim-bookworm` pinned digest in `Containerfile` to the latest upstream value while keeping the same tag
- **Pre-commit hook removal transform preserves section comments** ([#171](https://github.com/vig-os/devcontainer/issues/171))
  - `scripts/transforms.py` keeps section comments intact while removing configured hooks during manifest sync
  - `scripts/manifest.toml` and related sync/test updates keep workspace pre-commit outputs aligned with container CI workflow changes
- **Migrate shared scripts into `vig-utils` package entrypoints** ([#217](https://github.com/vig-os/devcontainer/issues/217), [#161](https://github.com/vig-os/devcontainer/issues/161), [#179](https://github.com/vig-os/devcontainer/issues/179))
  - Shell scripts (`check-skill-names.sh`, `derive-branch-summary.sh`, `resolve-branch.sh`, `setup-labels.sh`) bundled inside `vig_utils.shell` and exposed as `vig-<name>` CLI entrypoints
  - Python scripts (`gh_issues.py`, `check-agent-identity.py`, `check-pr-agent-fingerprints.py`, `prepare-commit-msg-strip-trailers.py`) migrated into `vig-utils` modules with entrypoints
  - Agent fingerprint helpers consolidated into shared `vig_utils.utils` module
  - Callers (justfiles, pre-commit hooks, CI workflows) switched from direct script paths to `vig-utils` entrypoints
- **Restructure workspace justfile into devc/project split** ([#219](https://github.com/vig-os/devcontainer/issues/219))
  - Rename `justfile.base` to `justfile.devc` and keep devcontainer lifecycle recipes there
  - Move project-level recipes (`lint`, `format`, `precommit`, `test`, `sync`, `update`, `clean-artifacts`, `log`, `branch`) into `justfile.project`
  - Add tracked `justfile.local` template for personal recipes while keeping it ignored in downstream workspaces, and update workspace imports/manifests to the new structure
- **Update base Python image and GitHub Actions dependencies** ([#240](https://github.com/vig-os/devcontainer/issues/240))
  - Containerfile: pin `python:3.12-slim-bookworm` to latest digest
  - Bump trivy CLI v0.69.2 → v0.69.3, trivy-action v0.33.1 → v0.35.0
  - Update astral-sh/setup-uv, taiki-e/install-action, docker/build-push-action, github/codeql-action, actions/dependency-review-action, actions/attest-build-provenance
- **Bump GitHub CLI to 2.88.x**
  - Update expected `gh` version in image tests from 2.87 to 2.88
- **Manifest sync includes `sync-main-to-dev` workflow** ([#278](https://github.com/vig-os/devcontainer/issues/278))
  - Add `.github/workflows/sync-main-to-dev.yml` to `scripts/manifest.toml` so workspace sync includes the release-to-dev PR automation workflow


### Removed

- **`post-release.yml`** — replaced by `sync-main-to-dev.yml` ([#172](https://github.com/vig-os/devcontainer/issues/172))
- **`scripts/prepare-build.sh`** — merged into `build.sh` ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **`scripts/sync-prs-issues.sh`** — deprecated sync script ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **`test.yml` workflow** — replaced by `ci.yml` ([#48](https://github.com/vig-os/devcontainer/issues/48))
- **Stale `.github_data/` directory** — 98 files superseded by `docs/issues/` and `docs/pull-requests/` ([#91](https://github.com/vig-os/devcontainer/issues/91))
- **Legacy standalone script copies** ([#217](https://github.com/vig-os/devcontainer/issues/217))
  - Removed `scripts/check-agent-identity.py`, `scripts/check-skill-names.sh`, `scripts/derive-branch-summary.sh`, `scripts/resolve-branch.sh` — now in `vig-utils`
  - Removed `assets/workspace/.devcontainer/scripts/gh_issues.py`, `check-pr-agent-fingerprints.py`, `prepare-commit-msg-strip-trailers.py` — now in `vig-utils`
  - Removed `scripts/utils.py` shim — superseded by `vig_utils.utils`

### Fixed

- **`just` default recipe hidden by lint recipe** ([#254](https://github.com/vig-os/devcontainer/issues/254))
  - The `default` recipe must appear before any other recipe in the justfile; `lint` was placed first, shadowing the recipe listing
  - Moved `default` recipe above `lint` to restore `just` with no arguments showing available recipes
- **Broken `gh-issues --help` guard in justfile recipe** ([#173](https://github.com/vig-os/devcontainer/issues/173))
  - `gh-issues` CLI has no `--help` flag, so the availability check always failed even when the binary was installed
  - Removed the broken guard; binary availability is now verified by the image test suite
- **Smoke-test redeploy preserves synced docs directories** ([#262](https://github.com/vig-os/devcontainer/issues/262))
  - `init-workspace.sh --smoke-test` now excludes `docs/issues/` and `docs/pull-requests/` from `rsync --delete`
  - Re-deploying smoke assets no longer removes docs synced by `sync-issues`
- **Prepare-release uses scoped app tokens for protected branch writes** ([#268](https://github.com/vig-os/devcontainer/issues/268))
  - `prepare-release.yml` now uses `COMMIT_APP_*` for git/ref and `commit-action` operations that touch `dev` and release refs
  - Draft PR creation in prepare-release now uses `RELEASE_APP_*` token scope for pull-request operations
- **generate-docs picks up unreleased TBD version on release branches** ([#271](https://github.com/vig-os/devcontainer/issues/271))
  - `get_version_from_changelog()` and `get_release_date_from_changelog()` now skip entries without a concrete release date
- **PR fingerprint check false positives on plain-text AI tool mentions** ([#274](https://github.com/vig-os/devcontainer/issues/274))
  - `contains_agent_fingerprint` now restricts name matching to attribution-context lines (e.g. "generated by", "authored by") instead of scanning the entire content
  - Wire up `allow_patterns` from `agent-blocklist.toml` to strip known-safe text (dotfile paths, doc filenames) before checking
- **Release candidate publish retags loaded images before push** ([#281](https://github.com/vig-os/devcontainer/issues/281))
  - `release.yml` now tags `ghcr.io/vig-os/devcontainer:X.Y.Z-arch` artifacts as `X.Y.Z-rcN-arch` before `docker push` in candidate runs
  - Prevents publish failures caused by pushing candidate tags that were never created locally after `docker load`
- **Pinned commit-action to the malformed path fix release** ([#286](https://github.com/vig-os/devcontainer/issues/286))
  - Updated smoke-test and release-related workflows to `vig-os/commit-action@c0024cbad0e501764127cccab732c6cd465b4646` (`v0.1.5`)
  - Resolves failures when commit-action receives `FILE_PATHS: .` and accidentally includes invalid `.git/*` tree paths
- **Smoke-test deploy commit no longer references non-local issue IDs** ([#284](https://github.com/vig-os/devcontainer/issues/284))
  - `assets/smoke-test/.github/workflows/repository-dispatch.yml` no longer injects `Refs: #258` into automated `chore: deploy <tag>` commits in the smoke-test repository
  - Added maintainer note that workflow-template changes require manual redeploy to `vig-os/devcontainer-smoke-test` and promotion through PRs to `main`
- **Install name sanitization trims invalid package boundaries** ([#291](https://github.com/vig-os/devcontainer/issues/291))
  - `install.sh` now normalizes sanitized project names to ensure they start/end with alphanumeric characters before passing `SHORT_NAME`
  - `init-workspace.sh` mirrors the same normalization so generated `pyproject.toml` names cannot end with separators like `_`

### Security

- **Eliminated 13 transitive vulnerabilities in BATS test dependencies** ([#37](https://github.com/vig-os/devcontainer/issues/37))
  - Bumped bats-assert from v2.1.0 to v2.2.0, which dropped a bogus runtime dependency on the `verbose` npm package
  - Removed entire transitive dependency tree: engine.io, debug, node-uuid, qs, tough-cookie, ws, xmlhttprequest, form-data, request, sockjs, and others (50+ packages reduced to 5)
  - Cleaned 13 now-unnecessary GHSA exceptions from `.github/dependency-review-allow.txt`
- **Go stdlib CVEs from gh binary accepted and documented** ([#37](https://github.com/vig-os/devcontainer/issues/37))
- CVE-2025-68121, CVE-2025-61726, CVE-2025-61728, CVE-2025-61730 added to `.trivyignore`
- Vulnerabilities embedded in statically-linked GitHub CLI binary; low exploitability in devcontainer context
- Each entry includes risk assessment, justification, and 3-month expiration date to force re-review
- Awaiting upstream `gh` release with Go 1.25.7 or later
- **GHSA-wvrr-2x4r-394v (bats-file false positive) accepted in dependency review** ([#37](https://github.com/vig-os/devcontainer/issues/37))
- Added to `.github/dependency-review-allow.txt` with 6-month expiration date enforced by CI
- **Upgraded pip** in Containerfile to fix CVE-2025-8869 (symbolic link extraction vulnerability) ([#37](https://github.com/vig-os/devcontainer/issues/37))
- **Digest-pinned base image** (`python:3.12-slim-bookworm`) with SHA256 checksum verification for all downloaded binaries and `.trivyignore` risk-assessment policy in Containerfile ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Minisign signature verification** for cargo-binstall downloads ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **GitHub Actions and Docker actions pinned to commit SHAs** across all workflows ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Pre-commit hook repos pinned to commit SHAs** ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Workflow permissions hardened** with least-privilege principle and explicit token scoping ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Input sanitization** — inline expression interpolation replaced with environment variables in workflow run blocks to prevent injection ([#50](https://github.com/vig-os/devcontainer/issues/50))
- **Update vulnerable Python dependencies** ([#88](https://github.com/vig-os/devcontainer/issues/88))
  - Add uv constraints for transitive dependencies: `urllib3>=2.6.3`, `filelock>=3.20.3`, and `virtualenv>=20.36.1`
  - Regenerate `uv.lock` with patched resolutions (`urllib3 2.6.3`, `filelock 3.25.0`, `virtualenv 21.1.0`)
- **Temporary Trivy exception for CVE-2025-15558 in gh binary** ([#122](https://github.com/vig-os/devcontainer/issues/122))
  - Added `CVE-2025-15558` to `.trivyignore` with risk assessment, upstream dependency context, and an expiration date
  - Keeps CI vulnerability scan unblocked while waiting for an upstream `gh` release that includes the patched `github.com/docker/cli` dependency

## [0.2.1](https://github.com/vig-os/devcontainer/releases/tag/0.2.1) - 2026-01-28

### Added

- **Manual target branch specification** for sync-issues workflow
  - Added `target-branch` input to `workflow_dispatch` trigger for manually specifying commit target branch
  - Allows explicit branch selection when triggering workflow manually (e.g., `main`, `dev`)
- **cargo-binstall** in Containerfile
  - Install via official install script; binaries in `/root/.cargo/bin` with `ENV PATH` set
  - Version check in `tests/test_image.py`
- **typstyle** linting
  - Install via `cargo-binstall` in Containerfile
  - Version check in test suite
  - Pre-commit hook configuration for typstyle
- **Just command runner** installation and version verification
  - Added installation of the latest version of `just` (1.46.0) in the Containerfile
  - Added tests to verify `just` installation and version in `test_image.py`
  - Added integration tests for `just` recipes (`test_just_default`, `test_just_help`, `test_just_info`, `test_just_pytest`)
- **GitHub Actions workflow for multi-architecture container image publishing** (`.github/workflows/release.yml`)
  - Automated build and publish workflow triggered on semantic version tags (X.Y.Z)
  - Multi-architecture support (amd64, arm64) with parallel builds on native runners
  - Image testing before push: runs `pytest tests/test_image.py` against built images
  - Manual dispatch support for testing workflow changes without pushing images (default version: 99.0.1)
  - Optional manual publishing: `workflow_dispatch` can publish images/manifests when `publish=true` (default false)
  - Architecture validation and dynamic selection: users can specify single or multiple architectures (amd64, arm64) with validation
  - Comprehensive error handling and verification steps
  - OCI-standard labels via `docker/metadata-action`
  - Build log artifacts for debugging (always uploaded for manual dispatch and on failure)
  - Multi-architecture manifest creation for automatic platform selection
  - Centralized version extraction job for reuse across build and manifest jobs
  - Concurrency control to prevent duplicate builds
  - Timeout protection (60 minutes for builds, 10 minutes for manifest)
- **GitHub Actions workflow for syncing issues and PRs** (`.github/workflows/sync-issues.yml`)
  - Automated sync of GitHub issues and PRs to markdown files in `.github_data/`
  - Runs on schedule (daily), manual trigger, issue events, and PR events
  - Smart branch selection: commits to `main` when PRs are merged into `main`, otherwise commits to `dev`
  - Cache-based state management to track last sync timestamp
  - Force update option for manual workflow dispatch
- **Enhanced test suite**
  - Added utility function tests (`tests/test_utils.py`) for `sed_inplace` and `update_version_line`
  - Improved test organization in justfile with grouped test commands (`just test-all`, `just test-image`, `just test-utils`)
- **Documentation improvements**
  - Added workflow status badge to README template showing publish workflow status
  - Simplified contribution guidelines by removing QEMU build instructions

### Changed

- **Sync-issues workflow branch protection bypass**
  - Added GitHub App token generation step using `actions/create-github-app-token@v2`
  - Updated commit-action to use GitHub App token for bypassing branch protection rules
  - Updated `vig-os/commit-action` from `v0.1.1` to `v0.1.3`
  - Changed commit-action environment variable from `GITHUB_TOKEN`/`GITHUB_REF` to `GH_TOKEN`/`TARGET_BRANCH` to match action's expected interface
- **Devcontainer test fixtures** (`tests/conftest.py`)
  - Shared helpers for `devcontainer_up` and `devcontainer_with_sidecar`: path resolution, env/SSH, project yaml mount, run up, teardown
  - `devcontainer_with_sidecar` scope set to session (one bring-up per session for sidecar tests)
  - Cleanup uses same approach as `just clean-test-containers` (list containers by name, `podman rm -f`) so stacks are torn down reliably
  - Redundant imports removed; fixture logic simplified for maintainability
- **Build process refactoring**
  - Separated build preparation into dedicated `prepare-build.sh` script
  - Handles template replacement, asset copying, and README version updates
  - Improved build script with `--no-cache` flag support and better error handling
- **Development workflow streamlining**
  - Simplified contribution guidelines: removed QEMU build instructions and registry testing complexity
  - Consolidated test commands in justfile for better clarity
  - Updated development setup instructions to reflect simplified workflow
- **Package versions**
  - Updated `ruff` from 0.14.10 to 0.14.11 in test expectations

### Removed

- **Deprecated justfile test recipe and test**
  - Removed deprecated test command from justfile
  - Removed deprecated test for default recipe in justfile (`TestJustIntegration.test_default_recipe_includes_check`)
- **Registry testing infrastructure** (moved to GitHub Actions workflow)
  - Removed `scripts/push.sh` (455 lines) - functionality now in GitHub Actions workflow
  - Removed `tests/test_registry.py` (788 lines) - registry tests now in CI/CD pipeline
  - Removed `scripts/update_readme.py` (80 lines) - README updates handled by workflow
  - Removed `scripts/utils.sh` (75 lines) - utilities consolidated into other scripts
  - Removed `just test-registry` command - no longer needed with automated workflow

### Fixed

- **Multi-platform container builds** in Containerfile
  - Removed default value from `TARGETARCH` ARG to allow Docker BuildKit's automatic platform detection
  - Fixes "Exec format error" when building for different architectures (amd64, arm64)
  - Ensures correct architecture-specific binaries are downloaded during build
- **Image tagging after podman load** in publish workflow
  - Explicitly tag loaded images with expected name format (`ghcr.io/vig-os/devcontainer:VERSION-ARCH`)
  - Fixes test failures where tests couldn't find the image after loading from tar file
  - Ensures proper image availability for testing before publishing
- **GHCR publish workflow push permissions**
  - Authenticate to `ghcr.io` with the repository owner and token context, and set explicit job-level `packages: write` permissions to prevent `403 Forbidden` errors when pushing layers.
- **Sync-issues workflow branch determination logic**
  - Fixed branch selection to prioritize manual `target-branch` input when provided via `workflow_dispatch`
  - Improved branch detection: manual input → PR merge detection → default to `dev`
- **Justfile default recipe conflict**
  - Fixed multiple default recipes issue by moving `help` command to the main justfile
  - Removed default command from `justfile.project` and `justfile.base` to prevent conflicts
  - Updated just recipe tests to handle variable whitespace in command output formatting
- **Invalid docker-compose.project.yaml**
  - Added empty services section to docker-compose.project.yaml to fix YAML validation
- **Python import resolution in tests**
  - Fixed import errors in `tests/test_utils.py` by using `importlib.util` for explicit module loading
  - Improved compatibility with static analysis tools and linters
- **Build script improvements**
  - Fixed shellcheck warnings by properly quoting script paths
  - Improved debug output and error messages

## [0.2.0](https://github.com/vig-os/devcontainer/releases/tag/0.2.0) - 2026-01-06

### Added

- **Automatic version check** for devcontainer updates with DRY & SOLID design
  - Checks GitHub API for new releases and notifies users when updates are available
  - Silent mode with graceful failure (no disruption to workflow)
  - Configurable check interval (default: 24 hours) with spam prevention
  - Mute notifications for specified duration (`just check 7d`, `1w`, `12h`, etc.)
  - Enable/disable toggle (`just check on|off`)
  - One-command update: `just update` downloads install script and updates template files
  - Configuration stored in `.devcontainer/.local/` (gitignored, machine-specific)
  - Auto-runs on `just` default command (can be disabled)
  - Comprehensive test suite (`tests/test_version_check.py`) with 24 tests covering all functionality
- **One-line install script** (`install.sh`) for curl-based devcontainer deployment
  - Auto-detection of podman/docker runtime (prefers podman)
  - Auto-detection and sanitization of project name from folder name (lowercase, underscores)
  - OS-specific installation instructions when runtime is missing (macOS, Ubuntu, Fedora, Arch, Windows)
  - Runtime health check with troubleshooting advice (e.g., "podman machine start" on macOS)
  - Flags: `--force`, `--version`, `--name`, `--dry-run`, `--docker`, `--podman`, `--skip-pull`
- `--no-prompts` flag for `init-workspace.sh` enabling non-interactive/CI usage
- `SHORT_NAME` environment variable support in `init-workspace.sh`
- Test suite for install script (`tests/test_install_script.py`) with unit and integration tests
- `just` as build automation tool (replaces `make`)
- Layered justfile architecture: `justfile.base` (managed), `justfile.project` (team-shared), `justfile.local` (personal)
- Generic sidecar passthrough: `just sidecar <name> <recipe>` for executing commands in sidecar containers
- Documentation generation system (`docs/generate.py`) with Jinja2 templates
- Python project template with `pyproject.toml` and standard structure (`src/`, `tests/`, `docs/`)
- Pre-built Python virtual environment with common dev/science dependencies (numpy, scipy, pandas, matplotlib, pytest, jupyter)
- Auto-sync Python dependencies on container attach via `uv sync`
- `UV_PROJECT_ENVIRONMENT` environment variable for instant venv access without rebuild
- `pip-licenses` pre-commit hook for dependency license compliance checking (blocks GPL-3.0/AGPL-3.0)
- Pre-flight container cleanup check in test suite with helpful error messages
- `just clean-test-containers` recipe for removing lingering test containers
- `PYTEST_AUTO_CLEANUP` environment variable for automatic test container cleanup
- `docker-compose.project.yaml` for team-shared configuration (git-tracked, preserved during upgrades)
- `docker-compose.local.yaml` for personal configuration (git-ignored, preserved during upgrades)
- Build-time manifest generation for optimized placeholder replacement
- `tests/CLEANUP.md` documentation for test container management

### Changed

- `ORG_NAME` now defaults to `"vigOS/devc"` instead of requiring user input
- `init-workspace.sh` now escapes special characters in placeholder values (fixes sed errors with `/` in ORG_NAME)
- Documentation updated with curl-based install as primary quick start method
- **BREAKING**: Replaced `make` with `just` - all build commands now use `just` (e.g., `just test`, `just build`, `just push`)
- **Versioning scheme**: Switched from X.Y format to Semantic Versioning (X.Y.Z format).
All new releases use MAJOR.MINOR.PATCH format (e.g., 0.2.0).
The previous v0.1 release is kept as-is for backwards compatibility.
- **Package versions**: Bumped tool and project versions from previous release:
  - `uv` (0.9.17 → 0.9.21)
  - `gh` (2.83.1 → 2.83.2)
  - `pre-commit` (4.5.0 → 4.5.1)
  - `ruff` (0.14.8 → 0.14.10)
- VS Code Python interpreter now points to pre-built venv (`/root/assets/workspace/.venv`)
- Test container cleanup check runs once at start of `just test` instead of each test phase
- **BREAKING**: Docker Compose file hierarchy now uses `project.yaml` and `local.yaml` instead of `override.yml`
- Socket detection prioritizes Podman over Docker Desktop on macOS and Linux
- `{{TAG}}` placeholder replacement moved to container with build-time manifest generation (significantly faster initialization)
- Socket mount configuration uses environment variable with fallback: `${CONTAINER_SOCKET_PATH:-/var/run/docker.sock}`
- `initialize.sh` writes socket path to `.env` file instead of modifying YAML directly
- `init-workspace.sh` simplified: removed cross-platform `sed` handling (always runs in Linux)

### Removed

- Deprecated `version` field from all Docker Compose files
- `:Z` SELinux flag from socket mounts (incompatible with macOS socket files)
- `docker-compose.override.yml` (replaced by `project.yaml` and `local.yaml`)
- `docker-compose.sidecar.yaml` (merged into main `docker-compose.yml`)

### Fixed

- Test failures from lingering containers between test phases
(now detected and reported before test run; added `PYTEST_SKIP_CONTAINER_CHECK` environment variable)
- Improved error messages for devcontainer startup failures
- SSH commit signing: Changed `user.signingkey` from file path to email identifier to support SSH agent forwarding.
  Git now uses the SSH agent for signing by looking up the email in allowed-signers and matching with the agent key.
- Fixed `gpg.ssh.allowedSignersFile` path to use container path instead of host path after copying git configuration.
- Automatically add git user email to allowed-signers file during setup to ensure commits can be signed and verified.
- macOS Podman socket mounting errors caused by SELinux `:Z` flag on socket files
- Socket detection during tests now matches runtime behavior (Podman-first)

## [0.1](https://github.com/vig-os/devcontainer/releases/tag/0.1) - 2025-12-10

### Core Image

- Development container image based on Python 3.12 (Debian Trixie)
- Multi-architecture support (AMD64, ARM64)
- System tools: git, gh (GitHub CLI), curl, openssh-client, ca-certificates
- Python tools: uv, pre-commit, ruff
- Pre-configured development environment with minimal overhead

### Devcontainer Integration

- VS Code devcontainer template with init-workspace script setting organization and project name
- Docker Compose orchestration for flexible container management
- Support for mounting additional folders via docker-compose.override.yml
- Container lifecycle scripts `post-create.sh`, `initialize.sh` and `post-attach.sh` for seamless development setup
- Automatic Git configuration synchronization from host machine
- SSH commit signing support with signature verification
- Focused `.devcontainer/README.md` with version tracking, lifecycle documentation, and workspace configuration guide
- User-specific `workspace.code-workspace.example` for multi-root VS Code workspaces (actual file is gitignored)

### Testing Infrastructure

- Three-tiered test suite: image tests, integration tests, and registry tests
- Automated testing with pytest and testinfra
- Registry tests with optimized minimal Containerfile (10-20s builds)
- Session-scoped fixtures for efficient test execution
- Comprehensive validation of push/pull/clean workflows
- Tests verify devcontainer README version in pushed images
- Helper function tests for README update utilities

### Automation and Tooling

- Justfile with build, test, push, pull, and clean recipes
- Automated version management and git tagging
- Automatic README.md updates with version and image size during releases
- Push script with multi-architecture builds and registry validation
- Setup script for development environment initialization
- `update_readme.py` helper script for patching README metadata (version, size, development reset)
- Automatic devcontainer README version updates during releases

### Documentation and Templates

- GitHub issue templates (bug report, feature request, task)
- Pull request template with comprehensive checklist
- Complete project documentation (README.md, CONTRIBUTE.md, TESTING.md)
- Detailed testing strategy and workflow documentation
- Push script updates README files in both project and assets
