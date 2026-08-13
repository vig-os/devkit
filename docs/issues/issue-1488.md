---
type: issue
state: closed
created: 2026-08-13T08:23:49Z
updated: 2026-08-13T11:26:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1488
comments: 4
labels: none
assignees: none
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:08.755Z
---

# [Issue 1488]: [guardrails as a capability module — the semantic-gate half of #1400](https://github.com/vig-os/devkit/issues/1488)

Splits the second half of #1400 out of the Rust-pack issue, now that the first half has landed (#1429). The Rust pack shipped; the reconciliation with `gerchowl/guardrails` has not started.

## Why

devkit ships **26 hooks to consumers and every one of them is syntactic** — formatting, whitespace, YAML/TOML/JSON validity, `typos`, commit-message shape. Useful, and not one of them can tell you the code does what it says.

Every *semantic* gate the org actually relies on lives in `gerchowl/guardrails`, a **personal repo**, consumed by `gerchowl/filesender` as a direct flake input:

`no-fake-impl` · `no-hardcoded` · `no-commented-code` · `no-debug-leftovers` · `no-raw-trace-fields` · `derived-docs` · `duplication` · `ci-shim` · `protect-trunk` · `protect-trunk-push` · `adr-matrix` · `numerical-obligation` · `no-conflict-markers` · `perf-budget` · `perf-record`

An org toolchain whose semantic enforcement depends on one person's account is a bus-factor question, and it is the reason this was filed in the first place.

## What guardrails actually is — it is four things, not one

~4,365 LOC. Treating it as a single unit is the mistake to avoid; the parts have different homes.

| part | size | nature | proposed home |
|---|---|---|---|
| `gates/*.sh` | 2,900 LOC shell, 15 gates | **language-agnostic** | devkit — `guardrails` capability module |
| `crates/trace` | ~130 LOC Rust | generic telemetry (`guardrails-trace` wraps every hook entry, emits JSONL) | devkit, alongside the gates |
| `tools/` (freshness, stale, nudge-ledger, diffpack) | shell | a distinct **nudge** subsystem — probabilistic, not gating | separate decision; do NOT fold into the gate module by default |
| `crates/tunables` | ~130 LOC Rust | `const_tunable!` / `config!` → generated `TUNABLES.md` | **Rust-specific** — belongs with the Rust pack, not an org-wide module |

Splitting `tunables` out matters: it is the one piece that would make a language-agnostic module carry Rust.

## The contract question — and it answers OPPOSITELY to #1427

A `guardrails` module's entire product is **hook entries**. The capability-module ADR excludes that from v1:

> **Hooks contribution** (e.g. `native` adding `clang-format` to the #883 consumer hook set) — open design question, recorded here for #883's wave

So this hits the same deferred question `rust` hit with `checks`. Applying the test #1427 settled on:

> If a field can be added to the shell composition contract without touching shell composition, it isn't part of that contract.

- **`checks`** could be added without touching shell composition at all → not part of it → shipped as `lib.mkRustProject`.
- **`hooks` cannot.** `mkProjectShell` already takes a `hooks` argument (#883) and *generating and installing the config is part of building the shell* — entering the shell installs it via git-hooks.nix. Hook entries fold monoidally, exactly like `packages`. They are on the shell's lifecycle, not `nix flake check`'s. And they need no consumer project shape, which was the disqualifier for `checks`.

**So `hooks` belongs in the contract and `checks` did not — reached with the same criterion.** That is the argument for extending to v2 here rather than bolting on another lib function, and it is worth stating plainly because the two decisions look contradictory from outside.

This is also what closes the deferred item honestly: the ADR recorded hooks-contribution as an open question awaiting a real consumer. `guardrails` is that consumer.

## Absorb, or take a flake input?

**Absorb.** Recommended, and it differs from how the Rust pack took `crane`/`fenix` for a reason:

- The gates are **2,900 lines of dependency-free shell**. There is no upstream to track, no version to follow, no build. Vendoring them costs nothing at eval and adds no lock node — the whole objection in #1440 evaporates.
- devkit already vendors its hook *definitions* (`nix/hooks.nix`); the gate scripts are the same category of thing.
- It removes the bus-factor problem outright rather than formalising it into a dependency.
- `guardrails` keeps its own repo as upstream/dev if wanted, but devkit must not *depend* on it.

The counter-argument — divergence between the two copies — is real and is why P0 includes retiring the standalone consumption path in `filesender` rather than running both.

## Gate versus nudge, and the tiering problem

Not all 15 are org-wide-safe. Some are opinionated enough that forcing them on every repo would get the whole module disabled — which is the failure mode that matters, because **a noisy gate trains `--no-verify`**.

Proposed default tiers, to be argued in review:

- **Gate by default** (deterministic, low false-positive): `no-conflict-markers`, `protect-trunk`, `protect-trunk-push`, `derived-docs`, `no-debug-leftovers`
- **Nudge by default** (probabilistic or style-adjacent): `duplication`, `no-commented-code`, `adr-matrix`, `ci-shim`
- **Opt-in** (needs project convention): `no-hardcoded`, `no-fake-impl`, `no-raw-trace-fields`, `numerical-obligation`, `perf-budget`, `perf-record`

`no-hardcoded` in particular fires on any bare literal and needs a `guardrails-ok` convention plus definition-site annotations before a repo can live with it; `gerchowl/filesender` has both and still needed per-file work.

## The ratchet, which is currently in the wrong place

guardrails already ships **`perf-budget`** (gate criterion medians / a bespoke JSON map against a committed budgets file, with fractional `tolerance`, `mode = gate|nudge`, and `direction = higher` for throughput) and **`perf-record`** (append a CSV history row per bench — "the PR diff IS the perf report").

The Rust pack independently grew a `perf-ratchet` check (#1429): binary size + dependency-graph size against `.repo/perf-baseline.toml`. **I wrote it without knowing perf-budget existed.**

The metrics are genuinely complementary — perf-budget gates *benchmarks you wrote*, the pack ratchet gates *deterministic artifact facts and needs no benches* — but **the mechanism is duplicated and guardrails' schema is the better one**: fractional tolerance, explicit gate/nudge, direction-aware. The pack's has a bare `tolerance_pct` and no nudge mode.

They should converge on one schema, and the generic half ("snapshot a metric, fail on growth, report improvement, reseal deliberately") is language-agnostic — only the collectors are Rust-shaped.

## Scope

**P0**
- [ ] Decide absorb-vs-input (recommendation: absorb)
- [ ] Extend the capability-module contract to v2 with `hooks`, and amend `ADR-capability-modules` — closing the deferred item with the #1427 criterion as the reasoning
- [ ] `nix/modules/guardrails.nix`: contributes hook entries + the toolbelt packages, with `tier` options so a consumer can move a gate between gate/nudge/off
- [ ] Vendor `gates/*.sh` + `guardrails-trace` into devkit, wired through `nix/hooks.nix`'s existing `yaml`/`check`/`consumer` triple so the drift gate covers them like every other hook
- [ ] Per-gate fixtures: known-bad fires, known-good stays quiet. Non-negotiable — the whole point is that an unexecuted gate reports nothing

**P1**
- [ ] Converge `perf-budget` and the Rust pack's `perf-ratchet` on one schema
- [ ] Decide the home for `tools/` (the nudge/freshness subsystem) — probably its own module, not this one
- [ ] Move `tunables` to the Rust pack

**P2**
- [ ] Retire `filesender`'s direct `guardrails` flake input; it becomes `modules = [ "guardrails" ]`
- [ ] Resolve Rust tool-config ownership (#1400 open question): guardrails ships its own `deny.toml` and clippy/rustfmt hook entries and so does the Rust pack — one owner, or the guardrails ones defer when the pack is present

## Pitfalls

- **`hooks` in the contract is a bigger change than `checks` would have been.** It touches `nix/hooks.nix`, the committed `.pre-commit-config.yaml`, the scaffold copy, and the drift test that pins all three. The zero-module invariant must survive byte-identical, as it did for `rust`.
- **Two sources of the same gate.** While `filesender` consumes guardrails directly AND devkit vendors it, they will drift. Sequence P0 and P2 close together.
- **Tiering is where this succeeds or fails.** Ship all 15 as hard gates and the first consumer disables the module. The tiers above are a starting proposal, not a conclusion.
- **`no-hardcoded` needs a convention, not just a script** (`guardrails-ok`, definition-site annotations). Shipping the gate without documenting the convention makes it unusable.
- **Vendoring forks the gates.** Accepted deliberately — but say so in the ADR, or the next person "fixes" the divergence by re-adding the input.
- **The gates assume a git repo and a POSIX shell.** Fine for devkit consumers; worth an explicit statement rather than an assumption.

## Acceptance

- [ ] A consumer gets every org-wide semantic gate from `modules = [ "guardrails" ]` and no flake input of their own
- [ ] devkit depends on no personal repository
- [ ] Every shipped gate has a fires-on-bad AND quiet-on-good fixture, executed in CI
- [ ] `devShells.<system>.default.drvPath` unchanged for a zero-module consumer
- [ ] `ADR-capability-modules` records the v2 `hooks` field, the criterion that admits it, and why the same criterion excluded `checks`
- [ ] A consumer can demote any gate to nudge or off without forking devkit

## References

- #1400 (parent — the Rust half landed in #1429), #1427 (the `checks` decision and its criterion), #1440 (input-cost precedent), #1430, #1480
- `docs/rfcs/ADR-capability-modules.md` — the deferred hooks-contribution item
- `nix/hooks.nix` — the `yaml`/`check`/`consumer` triple any vendored gate must fill
- `gerchowl/guardrails` @ 5a61998 — 15 gates, `crates/{trace,tunables}`, `tools/`
- `gerchowl/filesender` — the only current consumer, wiring guardrails by hand today

Refs: #1400

---

# [Comment #1]() by [gerchowl]()

_Posted on August 13, 2026 at 08:45 AM_

## Decision: devkit owns the implementation, `gerchowl/guardrails` is deprecated

Upgrading the recommendation above from **absorb** to **absorb and retire**. Absorb-but-keep-upstream was the cautious version and it is the wrong trade here: it leaves two copies of 2,900 lines of shell with no version relationship, and my own pitfall list already flagged that they will drift. Retirement removes the pitfall instead of managing it.

This also deletes the "vendoring forks the gates" caveat entirely — there is nothing to fork from once the source of truth moves.

**devkit is already the right owner.** It owns the hook SSoT (`nix/hooks.nix`) with a drift gate pinning the `yaml`/`check`/`consumer` triple for every hook. A second, separately-versioned source of hook entries is redundant with a mechanism devkit already has and tests.

The window is also now: **`gerchowl/filesender` is the only consumer.** Retirement cost is one flake input today and grows with every repo that adopts guardrails in the meantime.

## Keep the NAME, retire the REPO

These are separate decisions and they should go different ways.

`guardrails-ok` is not an implementation detail — it is a **source-code convention that lives in consumer repos permanently**. In filesender alone:

| surface | count |
|---|---|
| `// guardrails-ok` annotations in Rust source | 21 |
| `GUARDRAILS_*` env vars (`GUARDRAILS_OUTPUT_GLOBS`) | 2 |
| `guardrails-*` hook ids / entries | 16 |
| docs referencing it | 3 |

Renaming to `devkit-ok` / `vigos-ok` would be a breaking change to every consumer's **source code**, for no functional gain, needing a migration and a compatibility period — and that surface only grows with adoption. It would also be the worse name: devkit is the *delivery mechanism*; "guardrails" is the *concept*. devkit already ships hooks under upstream ids (`check-added-large-files`, `ruff`, `typos`) without renaming them to match itself.

**So: `gates/` moves under devkit's tree, the repo is archived, and hook ids, the `guardrails-ok` annotation and the `GUARDRAILS_*` env vars all stay byte-identical.** A consumer's migration is deleting a flake input and adding `modules = [ "guardrails" ]` — no source changes.

## Precondition: 1,126 LOC needs a home before the repo can be archived

The gates are 2,900 LOC and clearly belong in devkit. The rest does not automatically follow, and archiving without deciding would silently drop it:

| part | LOC | where |
|---|---|---|
| `crates/trace` — `guardrails-trace`, the JSONL telemetry every hook entry wraps | ~130 | devkit, with the gates. Non-optional: every hook entry invokes it |
| `crates/tunables` — `const_tunable!` / `config!` → generated `TUNABLES.md` | ~130 | **Rust pack.** The one Rust-specific piece; keeping it here is what would make a language-agnostic module carry Rust |
| `tools/` — freshness, stale, nudge-ledger, diffpack, trace-report | ~870 | **Undecided, and the real open question.** This is a nudge/telemetry subsystem, not gating: probabilistic prompts, a ledger of what was nudged, staleness tracking. It is a different concept from a gate and should not be folded into this module by default |

`tools/` is the item that could stall the archive. Three honest options: a second `nudges` capability module; keep it as a small standalone tool devkit does not depend on; or drop it and lose the freshness/ledger idea. **It should not be smuggled into the gate module to avoid deciding.**

## Revised sequencing

1. Extend the contract to v2 with `hooks` (unchanged from above)
2. Vendor `gates/` + `crates/trace` into devkit, ids and annotations unchanged
3. Per-gate fires-on-bad / quiet-on-good fixtures
4. `filesender` drops the flake input, adopts `modules = [ "guardrails" ]` — zero source changes
5. Move `tunables` to the Rust pack
6. **Decide `tools/`**
7. Archive `gerchowl/guardrails` with a README pointing at devkit

Steps 1–4 are the P0. Step 7 is blocked on 5 and 6, not on 1–4 — so devkit can own the implementation and consumers can migrate well before the archive button is pressed.

Refs: #1400


---

# [Comment #2]() by [gerchowl]()

_Posted on August 13, 2026 at 08:55 AM_

## Decision: implementation medium for the gates

The obvious question once devkit owns the implementation: is `sh` the right medium, or should the gates be ported to xtask / Python / Rust? Measured rather than argued.

### The current shell does not justify a rewrite

| | |
|---|---|
| `shellcheck -S warning` across all 15 gates | **1 warning** |
| gates with tests | **15/15** (`test-gates.sh`, plus a dedicated `test-adr-matrix.sh`) |
| gates using `set -e` | **0/15 — and that is correct** |

The missing `-e` looks like the classic silent-failure bug and is not. These gates `grep`, and grep exits 1 on no-match; `set -e` would abort on the **quiet** path — turning "nothing to report" into a crash. They use `set -uo pipefail` with explicit `|| exit 2` where an abort is actually wanted. Deliberate, not sloppy.

So the port has to earn its way on something other than code quality, because the quality is there.

### `xtask` is structurally disqualified

Not a preference. `cargo-xtask` requires a Cargo workspace, and devkit serves Python-only, TypeScript and mixed repos — a Python consumer has no `Cargo.toml` to run it from. Org-wide gates must run where there is no Rust at all.

`gerchowl/filesender` uses an xtask for *its own* gates and that remains correct, because filesender is a Rust repo. It is a repo-local pattern, not an org one. Worth stating explicitly so the two do not get conflated later.

### Rust binary vs Python

**Rust binary** (not xtask) is viable: nix builds it, ships it on PATH, the consumer needs no cargo — exactly how `guardrails-trace` already ships today. Costs a 2,900-line rewrite, per-platform builds in devkit CI, and slower iteration on what is fundamentally "grep with judgment".

**Python / `vig-utils`** is devkit's native idiom. devkit already packages Python console scripts through the overlay, tests with pytest and lints with ruff + bandit; gates written there inherit that discipline instead of carrying a bespoke `test-gates.sh` harness and a second lint stack. Text scanning and regex are Python's strength. Costs interpreter startup across ~15 hooks on every commit (~0.5s), and shell expresses these particular pipelines more concisely.

### Decision

**No rewrite. Set the direction and let it pull.**

1. **The 15 existing gates stay in shell.** They are clean, fully tested, and the rewrite risk is asymmetric: a subtly-broken port **reports success**, which is precisely the failure class this module exists to prevent. Rewriting a working silent-failure detector into a possibly-broken one is a bad trade for consistency alone.
2. **New gates are written in Python (`vig-utils`)**, so the shell surface stops growing and the test/lint story converges over time rather than by decree.
3. **Port opportunistically, only where shell is genuinely the wrong tool.** There are exactly three such places, and they are all stateful/data-shaped rather than scanners:
   - the **perf ratchet** — structured TOML/JSON state, tolerance arithmetic, gate/nudge modes
   - **`perf-record`** — CSV history, per-commit row refresh
   - the **nudge ledger** in `tools/`

   The pure scanners (`no-hardcoded`, `no-fake-impl`, `no-commented-code`, …) are not on that list. Shell is a fine medium for "walk files, match patterns, report".

### Consequence for the existing plan

This lands on top of the P1 item already in this issue — converging the Rust pack's `perf-ratchet` with `perf-budget` onto one schema. **Do that one in Python.** It is the natural first native-medium gate: it is on the port-worthy list for independent reasons, it needs the richer schema (fractional tolerance, `mode = gate|nudge`, `direction`), and it proves the pattern on a single gate before anything else moves.

If that port goes badly, the answer is that shell stays and the direction was wrong — which is a much cheaper thing to learn on one gate than on fifteen.

Refs: #1400


---

# [Comment #3]() by [gerchowl]()

_Posted on August 13, 2026 at 09:07 AM_

## P0 attempted — two blockers found before any code landed

Branched `feature/1488-guardrails-module` off `dev` and started P0. Stopped and reverted; nothing is committed. Both blockers are cheap to clear but neither should be worked around silently.

### Blocker 1 — `gerchowl/guardrails` has no licence

No `LICENSE` file, no SPDX header anywhere in the tree, no `license` field in `Cargo.toml`, and the GitHub API reports `"license": null`.

Absent a licence, the default is all-rights-reserved. devkit is **Apache-2.0 and redistributes to every consumer**, so vendoring 3,794 lines of unlicensed shell into it would ship files carrying no grant. Worth noting the same gap already applies to `gerchowl/filesender`, which consumes guardrails today on an implicit grant, and that devkit itself runs `pip-licenses` and `cargo-deny` licence gates — vendoring unlicensed code into the repo that enforces licence policy is not a good look.

Trivial to clear, since it is the same owner: add `LICENSE` (Apache-2.0 matches devkit) or state the donation explicitly in the issue. **I did not copy a single file until this is settled.**

### Blocker 2 — the v2 `hooks` contract has an activation fork I under-thought

I wrote the contract change, and then checked what it does to an existing consumer. The design in the issue body is incomplete.

`mkProjectShell` gates the whole generated-hooks surface on `hooksEnabled = hooks != null || hooksExcludes != [ ]`. A module contributing hooks forces a choice:

- **Leave `hooksEnabled` alone.** A consumer with a committed `.pre-commit-config.yaml` (which is every consumer today, including filesender) composes a full gate set into a generator that never runs. Configured, believed active, enforcing nothing — the exact failure this module exists to prevent, caused by the module.
- **Let module hooks flip it on** (what I wrote). The install snippet correctly **refuses to overwrite a non-symlink `.pre-commit-config.yaml`** — so nothing is clobbered — but every committed-config consumer then gets a refusal WARNING on every `nix develop`, and the module's hooks stay inert anyway. Noise plus inertness.

Neither is acceptable, and the fix should follow the precedent this repo already set in #1427: **make the module refuse to load until the consumer has chosen a hook surface.** Either

```nix
hooks = { … };                       # generated surface — module hooks apply
```

or an explicit acknowledgement that the consumer owns its committed config and will wire the gates there itself. Exactly the shape of the `rust` module's mandatory `checks` option: loud at eval, with a documented opt-out, rather than silent.

That is a bigger design than "add a fourth field to the contract", and it belongs in the ADR amendment rather than being discovered by the first consumer.

I reverted rather than commit it. Zero-module parity was verified byte-identical while the change was in place, so the mechanism itself is sound — it is the activation semantics that need deciding.

### Revised P0

0. **Licence `gerchowl/guardrails`** (blocking, external to devkit)
1. Decide hook-surface activation: refuse-until-chosen (recommended), and write it into the ADR
2. Then the rest of P0 as filed — vendor gates, module, fixtures, filesender migrates

Steps 1 can proceed in parallel with 0; step 2 cannot start without 0.

Refs: #1400


---

# [Comment #4]() by [c-vigo]()

_Posted on August 13, 2026 at 11:26 AM_

Shipped in #1495: the `guardrails` capability module puts all 15 semantic gates plus the CLI, trace wrapper and freshness/stale/ledger tools (25 executables) on PATH, with `checks.guardrails-canary` asserting each gate actually fires on a known-bad fixture and stays quiet on a known-good one. Layer decision in #1492. Ships in 1.9.0.

