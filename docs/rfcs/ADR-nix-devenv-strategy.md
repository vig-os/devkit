---
rfc: ADR-nix-devenv-strategy
date: 2026-07-01
title: Org dev-environment strategy — activation, shell definition, and local services
status: accepted
authors:
  - Carlos Vigo (c-vigo)
---

# ADR: Nix dev-environment strategy across the vig-os org

**Decision (TL;DR):** The recurring "**direnv vs devenv vs devshell vs mkshell**"
question is a **category error** — it collapses **three separable axes** into one
four-way pick. Decomposed: **(1) activation** — keep `nix-direnv` as the org
default (with manual `nix develop` as the always-available fallback); **(2) shell
definition** — keep plain **`pkgs.mkShell`** (via the shared `mkProjectShell`
builder), and **reject** `numtide/devshell` and `cachix/devenv` as the shared
builder, because both interpose their own package-declaration surface between the
`devTools` single-source-of-truth and `PATH` (breaking the dev-shell↔image
**parity test**), and devenv additionally pays a ~165s import-from-derivation
(IFD) cold-eval tax and drags its own substituter; **(3) local services** — adopt
**`process-compose` + `juspay/services-flake`** as the nix-native `devenv up`
replacement for repos that need local MinIO/Postgres/etc., with the shared
`mkProjectServices` helper tracked separately (#795). This ADR is **authoritative
for `vig-os` repos** and a **recommendation** to `exo-pet`/`exoma` siblings.
Axes 1–2 largely *ratify* existing practice; axis 3 is the one genuinely open
decision this ADR settles.

## Problem Statement

`exo-fleet` issue [exo-pet/exo-fleet#76] proposes porting its dev-shell off
`cachix/devenv` to plain `pkgs.mkShell` to eliminate a measured cold-eval IFD
tax (~165s wall on a fresh worktree vs ~5s warm — devenv builds internal helper
derivations *during* evaluation). A comment there widens the question to "review
the differences/magic/potential of **devenv / devshell / mkshell / direnv**."

That four-item list is the trap this ADR exists to dispel: the four are **not
alternatives on one axis**. `direnv` is an **activation** mechanism; `mkShell` /
`devshell` / `devenv` are **shell-definition** mechanisms; and the local-service
orchestration people actually want from devenv (`devenv up`) is a **third**
concern that devenv merely *bundles* into its definition layer. Comparing them
head-to-head produces incoherent conclusions ("use direnv *instead of* devenv"
mixes an activation choice with a definition choice). The job of this ADR is to
name the axes, record what is already settled on each, and decide the one that
isn't.

### Current state, enumerated (`flake.nix` @ `dev`)

This repo — the `vig-os` toolchain SSoT — has already resolved axes 1 and 2 in
practice; the ADR makes that explicit and defensible.

**(A) Dual-mode delivery already ships.** `install.sh --mode
devcontainer|direnv|both` scaffolds either `.devcontainer/` (docker-compose →
published `ghcr.io/vig-os/devcontainer` image; heavy, full isolation) or
`flake.nix` + `.envrc` (nix-direnv → `vigos.lib.mkProjectShell`; light). The
"heavy devcontainer when isolation is needed **and** a lighter nix env" posture
is not aspirational — it is the current product. `CONTRIBUTE.md` already frames
the nix dev-shell as "an alternative to the devcontainer image … use whichever
fits your workflow."

**(B) The shared builder is plain `pkgs.mkShell`.** `mkProjectShell`
(`flake.nix:159-263`) is a thin `pkgs.mkShell` over the `devTools` package set —
no framework. It is exported as `self.lib.mkProjectShell` and consumed by the
downstream scaffold (`assets/workspace/flake.nix`) via a `vigos.url` flake input.

**(C) The image is built from the same `devTools` SSoT, and a parity test
enforces it.** The image is assembled by `dockerTools.buildLayeredImage` (no
Dockerfile) from the same `devTools`; `devShellTools = devShellToolNames pkgs`
(`flake.nix:400`) is the SSoT the parity test (`tests/test_flake_devshell.py`)
reads to guarantee dev-shell == image toolchain. This is the **hard architectural
constraint** that rules out `devshell`/`devenv` as the shared builder (see
Options).

**(D) Activation is nix-direnv, GC-rooted.** `.envrc` self-bootstraps
`nix-direnv` (pinned v3.0.6) so re-entry is instant and the dev-shell closure is
not garbage-collected; it degrades to bare `use flake`. `nix develop` still works
underneath.

**(E) The org already rejected devenv once.** Issue #27 ("Adopt Nix/devenv") is
recorded **Superseded** by the flake-SSoT epic (#625/#631/#637). The
devenv-vs-pure-flake question was adjudicated in favour of pure flake during that
migration; this ADR consolidates the rationale rather than reopening it.

**(F) The hooks mechanism is mid-convergence — toward the *same* target as
exo-fleet.** This repo is adopting `cachix/git-hooks.nix` with `package =
pkgs.prek`, exposing `checks.pre-commit` and dropping the standalone `pre-commit`
(#778, PR #791, closing #40). exo-fleet's #76 port likewise moves its hooks onto
`git-hooks.nix` (they were already declared as devenv's `git-hooks.hooks`). So
the two repos are landing on the **same** hooks substrate — which is what makes
recommending exo-fleet align low-friction rather than a forced coupling.

## The three axes

| Axis | What it decides | Exclusive? | Status |
|------|-----------------|------------|--------|
| **1 — Activation** | How you *enter* the env: `nix-direnv` (auto on `cd`, GC-rooted) vs manual `nix develop` | No — complementary; direnv sits *on top of* `nix develop` | **Settled:** nix-direnv default |
| **2 — Shell definition** | How the devShell is *defined*: `pkgs.mkShell` vs `numtide/devshell` vs `cachix/devenv` | Yes — one per repo | **Settled:** `mkShell` |
| **3 — Local services** | `devenv up`-style orchestration of dev services (MinIO/Postgres/…) | Orthogonal add-on to axis 2 | **Decided here:** process-compose + services-flake |

The reason the four-way question feels natural is that **devenv couples axis 2 and
axis 3** — it is both a shell-definition framework *and* a services runner. Naming
axis 3 as separable is what lets us keep `mkShell` (axis 2) *and* still get
`devenv up`-equivalent services (axis 3) without contradiction. `numtide/devshell`
sits purely on axis 2 (a TOML/menu ergonomics layer over `mkShell`); `direnv` is
purely axis 1.

## Options Considered

### Axis 1 — Activation

**A1 — `nix-direnv` (chosen).** Auto-activates on `cd`, caches the flake eval, and
GC-roots the closure so re-entry is instant and paths survive garbage collection.

- **Pros:** Zero-friction entry; the GC root is what keeps steady-state
  new-worktree spin-up at ~seconds; already the shipped default (`.envrc`, both
  install modes).
- **Cons:** Requires the user to install the direnv shell hook once; on a cold
  store the first `direnv allow` pays the full eval+realise cost (this is exactly
  what devenv's IFD amplifies — see B3).
- **Decision:** Keep as default.

**A2 — manual `nix develop` (complementary fallback).** Not an alternative to A1 —
it is the layer A1 automates, and remains the escape hatch for CI, non-direnv
shells, and debugging. No decision needed; document that it always works.

### Axis 2 — Shell definition

**B1 — `pkgs.mkShell` via `mkProjectShell` (chosen).**

- **Pros:** Standard library, **zero IFD**, zero extra flake inputs/substituters.
  Crucially, it keeps the `devTools` list as the *sole* declaration surface, so
  the dev-shell↔image **parity test** (C) stays trivially true. Already adopted by
  every `vig-os` flake (`devcontainer`, `scitadel`).
- **Cons:** No built-in services/`up` (axis 3) and no menu/help UX — both provided
  orthogonally where wanted (axis 3 helper; `just --list` already serves as the
  verb menu).
- **Decision:** Keep as the shared builder.

**B2 — `numtide/devshell`.**

- **Pros:** A `devshell.toml` + a nice `menu`/help banner and structured
  command/env declaration; still `mkShell` underneath, so no IFD.
- **Cons:** Interposes its own package/command declaration surface between the
  `devTools` SSoT and `PATH`, complicating the parity guarantee (C) for no
  capability we lack — `just` already *is* our verb menu. **No repo in any of the
  three orgs uses it**; there is no onboarding-UX demand signal.
- **Decision:** Rejected (recorded for completeness; the "devshell" in the
  original four-way question).

**B3 — `cachix/devenv`.**

- **Pros:** Batteries-included — `languages`, `services`, `processes`, `devenv
  up`, a rich `git-hooks` wrapper. Genuinely convenient if you want axis 3 without
  wiring it yourself.
- **Cons:** **~165s IFD cold-eval** on a fresh worktree (measured, exo-fleet#76) —
  it builds internal helper derivations *during* evaluation, re-paid after every
  `flake.lock`/nixpkgs/devenv bump or GC eviction; **its own cachix substituter +
  key** in `nixConfig`; and it interposes a whole framework between `devTools` and
  `PATH`, fragmenting axis 2 across the org and complicating the parity test (C).
  This is the option #27 already superseded. exo-fleet uses exactly four devenv
  features — `packages`, one `env` var, an `enterShell` banner, and `git-hooks` —
  all trivially portable to `mkShell` + `git-hooks.nix`.
- **Decision:** Rejected as the shared builder. Permitted only as a bounded,
  documented per-repo exception (see *Reconsider if*).

### Axis 3 — Local services

The one open question: a repo drops devenv now, but *later* wants local
MinIO/Postgres for development. What replaces `devenv up`?

**C1 — `docker-compose` / `podman-compose`.** A `compose.yaml` started by a `just`
verb — already the mechanism the devcontainer mode uses.

- **Pros:** Universally understood; canonical upstream images; zero Nix-eval cost;
  identical in CI; the repo already ships a `docker`→`podman` wrapper.
- **Cons:** Requires a running container **daemon on the host** — reintroducing
  exactly the dependency the light direnv mode exists to avoid. Service *versions*
  live outside the nixpkgs lock (image tags), losing single-lockfile
  reproducibility for the data plane; not GC-rooted with the shell.
- **Decision:** Acceptable **only** when the repo already requires a container
  runtime (e.g. it runs in devcontainer mode against prod-parity images).

**C2 — `process-compose` + `juspay/services-flake` (chosen).** `process-compose`
is a single Go binary (TUI + declarative config, **no daemon, no root**) —
"compose for native processes." `services-flake` generates process-compose configs
for common services (postgres, minio, redis, mysql, …) from Nix. Exposed as `nix
run .#services` (or a `just up` verb) from inside a plain `pkgs.mkShell`.

- **Pros:** Native processes, **no container daemon** — preserves the light "no
  Docker" promise. Service versions come from the **same nixpkgs lock/SSoT** as
  the toolchain, so the data plane is reproducible and Renovate-tracked; GC-rooted
  with the flake; **no IFD**. It is the same lineage devenv shells out to under the
  hood — i.e. the `devenv up` *capability* without devenv's framework, cold-eval,
  or substituter. Directly replaces what exo-fleet#76 gives up.
- **Cons:** `services-flake` is idiomatically **flake-parts**, whereas the
  toolchain flakes are `flake-utils`/`eachSystem` (process-compose alone needs no
  flake-parts, so manual wiring is possible). Smaller service catalogue than
  compose; native (Nix-built) services can drift from the exact prod container
  image.
- **Decision:** **Adopt** as the org default services pattern. Shared
  `mkProjectServices` helper + a validating MinIO+Postgres PoC tracked in **#795**.

**C3 — re-add `devenv`, only in service-needing repos.**

- **Pros:** `services.postgres`/`services.minio` out of the box; `devenv up` in one
  command.
- **Cons:** Reintroduces the ~165s IFD, its own substituter, and a *second*
  shell-definition mechanism in the org (fragments axis 2). This is what #27
  superseded.
- **Decision:** Last-resort, bounded exception — only if a repo needs devenv's
  languages/services breadth services-flake genuinely can't match and can tolerate
  the cold-eval.

**C4 — plain `just` recipes wrapping `podman run`.** Matches the "we use `just` for
verbs" idiom.

- **Pros:** No new dependency beyond the existing podman wrapper; trivially
  readable for a *single* service.
- **Cons:** Hand-rolled ordering/health/teardown/networking that scales badly past
  ~2 services; daemon dependency like C1.
- **Decision:** Adequate single-service stopgap only.

#### Decision boundary — where each capability lives

Consolidating the split so it is unambiguous:

- **Toolchains** → Nix devShells: the shared `mkProjectShell` builder today, and
  future modular `vigos.devShells.{cpp,geant4,…}` as the org grows language
  stacks.
- **Local software services** (MinIO, Postgres, …) → `process-compose` +
  `services-flake` (C2), via the `mkProjectServices` helper (#795).
- The old **`docker-compose` sidecar / multi-container capability is removed**
  (#799). It predated this ADR and duplicated axis 3 with a daemon-bound,
  off-lock mechanism. The residual case it nominally covered — an opaque
  vendor/hardware image with no Nix expression — does not justify maintaining a
  bespoke sidecar `podman exec` framework; a repo in that spot uses a plain
  `compose.yaml` under a `just` verb (C1), gated by its already requiring a
  container runtime. The DooD socket for **building** containers inside the
  devcontainer is retained.

## Decision matrices

### Matrix 1 — Shell definition

| Criterion | `mkShell` / `mkProjectShell` | `numtide/devshell` | `cachix/devenv` |
|-----------|------------------------------|--------------------|-----------------|
| IFD / cold-eval cost | none | none | **~165s** (measured, #76) |
| Preserves dev-shell↔image parity SSoT | yes (trivial) | complicates | complicates |
| Extra flake inputs / substituters | 0 | 1 | 1 + own cache |
| Local services / `up` built-in | no (orthogonal) | no | yes |
| UX sugar (menu/help) | `just --list` | TOML menu | rich |
| Org adoption today | all `vig-os` flakes | none | exo-fleet only |
| Alignment w/ flake-SSoT posture (#27 superseded) | full | partial | rejected |

### Matrix 2 — Local services

| Criterion | `compose` (C1) | `process-compose`+`services-flake` (C2) | re-add `devenv` (C3) | `just`+podman (C4) |
|-----------|----------------|------------------------------------------|----------------------|--------------------|
| Host daemon required | yes | **no** | no | yes |
| Service versions in nixpkgs lock/SSoT | no | **yes** | yes | no |
| IFD cold-eval | none | none | ~165s | none |
| GC-rooted with shell | no | yes | yes | no |
| Prod-image parity | high | medium (Nix-built) | medium | high |
| Scales past ~2 services | yes | yes | yes | poor |
| flake-parts needed | no | yes (idiomatic) | no | no |
| Fits "just for verbs" idiom | partial | yes | no | yes |

## Impact

### Beneficiaries / blast radius

- **`vig-os` repos:** authoritative. `mkShell` + `mkProjectShell` + `nix-direnv`
  is the standard; new repos scaffold via `install.sh` and inherit it.
- **`exo-pet` / `exoma` siblings:** recommendation, not mandate. They live in orgs
  this repo does not own; convergence is encouraged where it fits.

### Migration

- **exo-fleet (#76):** ports `devenv.lib.mkShell` → plain `pkgs.mkShell` +
  `git-hooks.nix`, dropping the `devenv` input and `devenv.cachix.org`
  substituter. Its four devenv features port directly. This ADR *records* that
  this is an aligned instance of the pattern — exo-fleet keeps its **own** flake;
  it need **not** consume `mkProjectShell` the builder, which bakes the
  Python-devcontainer toolchain (`python314`/`uv`/`bats`) exo-fleet (NixOS infra)
  does not want. It adopts the **pattern** (mkShell + nix-direnv + git-hooks.nix),
  not that specific builder. The hooks mechanisms are already converging (F), so
  no divergence needs reconciling.
- **No `vig-os` repo changes** as a result of this ADR — it documents the status
  quo on axes 1–2 and opens #795 for axis 3.

### Compatibility

- No breaking change to existing `mkShell` repos; both `install.sh` modes are
  unaffected; the dev-shell↔image parity test is preserved (indeed, *protected* —
  it is a first-class reason for the axis-2 decision).

### Risks

- `services-flake`'s flake-parts affinity is a real wiring cost against the
  `flake-utils` toolchain flakes — surfaced and timeboxed in #795 (manual
  `process-compose` wiring is the fallback).
- Native (Nix-built) dev services can drift from prod container images; repos
  needing exact prod parity should prefer C1 for those specific services.
- The devenv exception (C3) risks re-fragmenting axis 2 if used casually — hence
  "bounded and documented" only.

## Decision & Recommendation

Adopt the three-axis framing as the standing answer to the "direnv vs devenv vs
devshell vs mkshell" question, and record per axis:

1. **Activation:** `nix-direnv` default; `nix develop` always available beneath it.
2. **Shell definition:** plain `pkgs.mkShell` via `mkProjectShell`; `devshell` and
   `devenv` rejected as the shared builder (parity-SSoT; devenv also IFD +
   substituter).
3. **Local services:** `process-compose` + `services-flake`, via the shared
   `mkProjectServices` helper (#795). Sketch of the target shape — a plain
   `mkShell` plus a services app:

   ```nix
   # illustrative; the real helper lands in #795
   services = import inputs.services-flake { inherit pkgs; } {
     services.minio."minio1".enable = true;
     services.postgres."pg1".enable = true;
   };
   # exposed as: nix run .#services   (no Docker/Podman daemon)
   ```

   Preference order when services are needed: **C2 preferred**; **C1** when a
   container runtime is already required; **C4** as a single-service stopgap;
   **C3** as a last-resort bounded exception.

### Reconsider if

- A `vig-os` repo needs local services **now** — pull #795 forward and let the
  MinIO+Postgres PoC validate C2 before others copy it.
- `services-flake`'s flake-parts requirement proves too costly in #795 — fall back
  to manual `process-compose` wiring (still C2, no framework) and record it.
- `numtide/devshell`'s menu UX becomes a real, repeated onboarding ask (currently
  zero demand) — revisit B2 as an *additive* ergonomics layer, not a replacement.
- A repo genuinely needs devenv's `languages`/`services` breadth that services-flake
  can't match **and** can tolerate the ~165s IFD — permit a bounded, documented
  per-repo devenv exception (C3), not an org default.

## References

- Related: [exo-pet/exo-fleet#76] (devenv→mkShell port; the cold-eval measurement);
  #27 (Adopt Nix/devenv — Superseded); #625/#631/#637 (flake-SSoT epic); #778 / PR
  #791 (git-hooks.nix + prek; closes #40); #795 (`mkProjectServices` helper —
  follow-up); this repo's #775 (uv2nix ADR) and #787 (secrets ADR) as sibling
  decision records.
- In-repo: [`flake.nix`](../../flake.nix) (`mkProjectShell` @159-263;
  `devShellTools` parity SSoT @400/450; `install.sh` modes),
  [`docs/NIX.md`](../NIX.md), [`CONTRIBUTE.md`](../../CONTRIBUTE.md),
  `assets/workspace/flake.nix`, `.envrc`.
- Upstream: `cachix/devenv`, `numtide/devshell`, `nix-community/nix-direnv`,
  `F1bonacc1/process-compose`, `juspay/services-flake`, `cachix/git-hooks.nix`.

[exo-pet/exo-fleet#76]: https://github.com/exo-pet/exo-fleet/issues/76
