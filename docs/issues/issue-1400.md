---
type: issue
state: open
created: 2026-08-10T12:34:30Z
updated: 2026-08-10T13:42:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1400
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:26.822Z
---

# [Issue 1400]: [Rust language pack — and reconciling devkit with gerchowl/guardrails](https://github.com/vig-os/devkit/issues/1400)

Two findings from building a full Rust layer on top of devkit 1.6.0 in
`gerchowl/filesender` (private). Design doc:
`docs/designs/0001-rust-language-pack.md` in that repo — it records the
verification status of every claim, including which remain unverified.

The second finding is the more urgent one, so it goes first.

---

# A. devkit and `gerchowl/guardrails` overlap, and today they collide

`gerchowl/guardrails` is "shareable code-quality / observability / perf
governance for repos — gates + toolbelt + conventions, packaged as a Nix flake…
built to counter agent drift". It is mature and shipping.

**The collision:** both projects want to own `.pre-commit-config.yaml`, both
install git hooks, and devkit additionally owns `.githooks/` and drives
`core.hooksPath`. A repo adopting both naively gets two hook managers fighting
over the same path — and the loser's hooks stop running *silently*, which is the
worst possible failure mode for a gate. Both also ship a `deny.toml` and both
ship templates.

**The overlap is otherwise complementary, not redundant:**

| | devkit | guardrails |
|---|---|---|
| Scaffold, delivery modes, `.vig-os` upgrades | ✅ | — |
| Release train, CI, commit standard | ✅ | — |
| Content gates (fake-impl, hardcoded, commented-code, conflict markers) | — | ✅ |
| Observability spine (`crates/trace`) + `no-raw-trace-fields` | — | ✅ |
| Tunables registry (`const_tunable!`/`config!` → generated `TUNABLES.md`) | — | ✅ |
| Perf budgets/ratchets, ADR-matrix, derived-docs freshness | — | ✅ |
| Capability modules, home-manager, image | ✅ | — |

So the question is not which wins — it is **who owns the hook surface**. Options:

1. devkit owns hooks; guardrails ships its gates as *entries* devkit's
   `.pre-commit-config.yaml` (or the flake-generated `hooks` argument) includes.
   The gates are already PATH-exposed as `guardrails-<name>`, so this looks
   cheap.
2. guardrails owns hooks; devkit's `prek` stack becomes a guardrails gate set.
3. Documented mutual exclusion — worst option, but honest if 1 and 2 are hard.

**Recommendation: option 1.** devkit's flake already supports fully custom hooks
via `mkProjectShell`'s `hooks` argument, which is exactly the seam, and
guardrails' gates are already individually invocable.

---

# B. Rust language pack

devkit is language-neutral by contract, and for Rust that currently means the
stock `justfile.project` guards every recipe on `[ -f pyproject.toml ]` — so on
a Rust repo **`just lint` and `just test` silently no-op and CI goes green
without compiling anything**. `nix/modules/default.nix` names `rust` as an
ask-gated candidate; this is the ask, with a working consumer behind it.

## Asks, in priority order

1. **Capability-module v1 cannot contribute `checks`.** The contract is
   `pkgs -> options -> { packages, env, shellHook }`, and most of a Rust pack's
   value *is* checks (clippy / fmt / nextest / doctests / deny). Either extend
   the contract, or bless `vigos.lib.mkRustProject` alongside `mkProjectShell`.
   **This decides the pack's shape** — a module-only adopter would get a
   toolchain and no checks, i.e. exactly the silent-green-CI failure above.
   Working within v1 for now: module for the toolchain, lib for the checks.

2. **The language axis is hardcoded.** Node support lives in a bash function
   (`seed_node_justfile_project`). Rust is the second language to need the same
   treatment; the fix is a `lang.d/<lang>/` pack the installer iterates, not a
   second special case.

3. **Nix detection false-negative.** Detection requires `*.nix` beyond
   `flake.nix`, so a single-flake repo is never nix-detected and never receives
   the nix `.gitignore` fragment — `result` / `result-*` go unignored. Every
   direnv-mode Rust consumer hits this.

4. **`worktree` opt-out leaves residue.** With the group disabled,
   `.claude/worktrees.json` survives and `.claude/skills/` is left as an empty
   directory.

5. **`contents: read` ceiling blocks the documented release-asset use case.**
   `release.yml` is managed, so raising it locally is reverted on the next
   `--force`. Options: raise it upstream, add an attach step to `release.yml`,
   or document OCI / `secrets: inherit` as the intended pattern.

## Known limits the pack has to state honestly

- **`flake.nix` is a `PRESERVE_FILE`**, so the Rust flake can never be
  scaffolded into an existing repo — template for new repos, documented snippet
  otherwise.
- **Cargo manifest policy cannot be scaffolded at all**; there is no
  manifest-merge. `[workspace.lints]`, profiles and resolver are template +
  documentation only. (Cargo also rejects mixing `lints.workspace = true` with
  crate-local overrides, so per-crate deviation must live in source as
  `#![allow(…)]` — which is actually the desirable shape: opt-out beats forget,
  and the opt-out is greppable.)
- **Policy files should be preserved (scaffold-once) + drift-reported.** A
  survey of uv / ruff / reth / rust-analyzer found ~70% overlap and ~30%
  **deliberate** divergence in `[workspace.lints]`. Enforcing a shared file
  would be wrong; reporting divergence is right.

## Evidence worth reusing

- Cross-repo `[workspace.lints]` sharing **does not exist** in Cargo (no
  manifest-fragment merge, no runtime to do it at — which is why npm's
  `eslint-config-*` pattern cannot be translated). Copy-paste is the state of
  the art.
- Orgs **do not** cross-consume reusable GitHub workflows —
  `uses: <org>/<repo>/…` searches across astral-sh, paradigmxyz and matter-labs
  return zero. They compose within-repo and pin actions by SHA.
- **Nix-flake-as-input is the only mechanism with real cross-repo distribution
  evidence** (crane, fenix — and guardrails). That validates both projects'
  approach.
- **Ship templates first, primitives second.** crane has ~30 lib primitives and
  14 `nix flake init -t` templates; the templates are what people adopt.
- **devkit already implements copier's update model** — `.vig-os` is
  `.copier-answers.yml` and `install.sh --force` is `copier update`. The gap
  versus copier is **migration hooks**: a version bump can re-render but cannot
  transform consumer files.
---

# [Comment #1]() by [gerchowl]()

_Posted on August 10, 2026 at 01:42 PM_

## Reconciliation: three layers, one hook surface

Following up on section A. The two systems were built independently — the
overlap is convergent rather than derivative, and the gaps are complementary.
Proposed division:

| Layer | Owns | Concretely |
|---|---|---|
| **devkit** | **WHO / WHEN** — identity, traceability, scaffold, release | `core.hooksPath`, commit-msg + prepare-commit-msg, `.vig-os`, CI, release train |
| **guardrails** | **WHAT** — content gates, conventions, toolbelt | the `guardrails-<name>` gates, `crates/trace`, tunables registry |
| **rust pack** | **HOW, for Rust** — toolchain and build correctness | fenix pin, crane checks, layering, fileset, profiles |

**devkit keeps the hook surface.** guardrails' gates enter as *entries* in the
`.pre-commit-config.yaml` devkit's flake generates — `mkProjectShell`'s `hooks`
argument is exactly that seam, and the gates are already individually invocable
as `guardrails-<name>`. The Rust pack adds further entries plus flake `checks`.
One surface, three contributors, nothing fighting over `core.hooksPath`.

### Stage assignment

| Stage | Budget | Contents | Owner |
|---|---|---|---|
| prepare-commit-msg / commit-msg | instant | template, Conventional + `Refs:` | devkit |
| pre-commit | milliseconds, greps only | gitleaks, `rustfmt --check`, no-conflict-markers, no-fake-impl, no-debug-leftovers, no-commented-code, no-hardcoded, no-raw-trace-fields, protect-trunk | guardrails |
| pre-push | seconds–minutes, needs a build | `clippy -D warnings`, nextest **+ `cargo test --doc`**, `cargo-deny`, xtask gates | rust pack |
| CI / PR | unbounded | `nix flake check`, mutants, perf budgets, numerical ratchet, coverage *report*, derived-docs, attribution freshness, scaffold drift | all three |
| scheduled | — | advisory DB re-scan, `guardrails stale` | guardrails |

Ordering rule: **earliest stage where it is fast enough.** A slow gate trains
`--no-verify`, and a bypassed gate is worse than no gate.

### What the Rust pack will NOT duplicate

guardrails does these better, so the pack consumes rather than reinvents:
the escape-hatch→generated-registry pattern (supersedes "every `#[allow]` carries
a reason"), `derived-docs` marker regions (supersedes per-artifact freshness
recipes), `no-raw-trace-fields` (supersedes a per-struct `Debug` test), plus
`no-fake-impl` and `protect-trunk`, which are agent failure modes the pack's
design had missed entirely.

### One principle adopted from guardrails that changes the pack

> A gate that demands a big-bang cleanup before it can be wired never gets wired.

Baseline ratchets — snapshot per-file counts, growth hard-fails, burn-down
nudges a re-record, at-baseline stays silent, re-recording refuses to loosen.
Every count-based gate in the pack needs that shape; without it a gate gets
deleted rather than satisfied.

### One gate that should go UPSTREAM to guardrails, not just into the pack

**Root tool configs must appear in the crane fileset.** A config absent from the
fileset is dropped inside the build sandbox, and the tool then runs against its
own defaults — **reporting success while enforcing nothing**. This bit the
consumer repo twice in one day (`deny.toml`, then `clippy.toml`, the latter
caught by the new gate on its first run, inside the very commit meant to fix
that class).

**guardrails' own gates are vulnerable to this** the moment they run inside a
crane sandbox with an explicit fileset. The failure is invisible by construction,
which is exactly what makes it worth a gate rather than a convention.

