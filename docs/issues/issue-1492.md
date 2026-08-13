---
type: issue
state: closed
created: 2026-08-13T09:14:33Z
updated: 2026-08-13T11:26:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1492
comments: 2
labels: none
assignees: none
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:07.332Z
---

# [Issue 1492]: [Decision: which layer owns module-contributed pre-commit hooks?](https://github.com/vig-os/devkit/issues/1492)

Split out of #1488, where I hit this while implementing and reverted rather than guess.

## The decision

A capability module wants to contribute **pre-commit hook entries**. For `guardrails` (#1488) that is not a nicety — hook entries are its *entire product*. Where do those entries go, and what happens to a consumer who is not set up to receive them?

## The mechanism today

`mkProjectShell` has **two mutually-exclusive hook surfaces**:

| surface | how it works | who is on it |
|---|---|---|
| **committed** | a real `.pre-commit-config.yaml` in the repo, seeded by the scaffold, run by `.githooks/pre-commit` → `prek run` | **every consumer today**, including `gerchowl/filesender` |
| **generated** | opt-in via `mkProjectShell { hooks = { … }; }`; git-hooks.nix renders a config into the store and the shellHook symlinks `.pre-commit-config.yaml` at it | nobody yet |

`hooksEnabled = hooks != null || hooksExcludes != [ ]` selects between them, and the install snippet **refuses to overwrite a non-symlink config** (correctly — it will not clobber your committed file).

## Why a module contributing hooks is not simply "add a fourth field"

On the **generated** surface, module entries merge cleanly. On the **committed** surface they have nowhere to go, and both available behaviours are bad:

- **Don't flip `hooksEnabled`** → the entries are silently discarded. A consumer writes `modules = [ "guardrails" ]`, believes 15 semantic gates are active, and has none. Configured, believed active, enforcing nothing — *caused by the module built to prevent exactly that*.
- **Flip it** → the install snippet refuses (nothing clobbered), prints a warning on every `nix develop`, and the entries are discarded anyway. Noise plus inertness.

So on the committed surface, module hooks **cannot work by construction**. The question is what to do about that.

## Three facts that may reshape the answer

1. **`.vig-os` already declares modules at the scaffold layer.** `DEVKIT_MODULES=""` exists today (#885: *"the scaffold-level declaration maps onto this flake-level contract — one name list, two layers"*). The committed `.pre-commit-config.yaml` is a scaffold-rendered artifact. **So hooks may belong to the scaffold layer, not the flake module contract at all** — which would make the whole "extend the contract to v2" framing in #1488 wrong.
2. **`prek` is not plain pre-commit.** `prek run --help` shows `-c/--config <CONFIG>` and a positional `[HOOK|PROJECT]...` — *"Include the specified hooks or projects"*. Whether prek supports multi-project/multi-config composition is a **factual question that could enable or kill several options**, and I have not established it.
3. **The precedent I would otherwise reach for may not apply.** #1427 settled that `checks` stays out of the contract and ships as a lib function, using the test *"if a field can be added to the shell composition contract without touching shell composition, it isn't part of that contract."* I argued in #1488 that `hooks` passes that test where `checks` failed. If hooks are really a *scaffold* concern, the test was applied to the wrong layer.

## Options

- **A — Refuse until the consumer chooses a surface.** Module throws at eval unless the consumer opts into the generated surface or explicitly acknowledges owning a committed config. Mirrors the `rust` module's mandatory `checks` option (#1427). Loud, but every existing consumer must act.
- **B — Scaffold-layer rendering.** `DEVKIT_MODULES` in `.vig-os` drives `init-workspace.sh` to render module hooks into the committed `.pre-commit-config.yaml` on scaffold/upgrade. Uses the layer that already owns that file. Cost: hooks only change on upgrade, and it splits module definition across two systems.
- **C — Package-only module + a drift gate.** The module contributes `packages` (the gate executables on PATH) and nothing else; a check asserts the committed config actually references them. No contract change at all. The consumer's config stays hand-owned and honest.
- **D — Merge into the committed config.** Read the committed YAML, splice module entries, write back. Most seamless, most invasive, and turns a hand-owned file into a partially-generated one.
- **E — Multi-config composition**, if `prek` genuinely supports it: ship module hooks as a second config the runner also reads. Depends entirely on fact 2.

## Pitfalls

- **Migration burden.** Every existing consumer is on the committed surface. Any option that requires them to move is a fleet-wide change, and "port your customizations into `mkProjectShell`'s hooks" is a real piece of work — filesender's config carries 16 hand-written gate entries wrapped in `guardrails-trace`.
- **Two definitions of the same hook.** If the module ships entries AND the scaffold seeds a committed config containing similar ones, they drift. devkit already has a drift gate for its own committed config vs `nix/hooks.nix`; a third source needs to join that discipline or be excluded from it.
- **Silence is the failure mode.** Whatever wins must make "module enabled, gates not running" *impossible or loud*. Detection after the fact is what this whole module exists to replace.
- **Option B splits the contract across layers**, so a consumer reading `nix/modules/guardrails.nix` would not see where its hooks actually come from.
- **Option D breaks the refusal semantics** that currently protect a consumer's committed file, and that refusal is load-bearing.

## Acceptance

- [ ] A decision, with the reasoning recorded where the next person will find it
- [ ] The layer question answered explicitly: scaffold, flake module contract, or both
- [ ] A stated migration path for consumers already on the committed surface
- [ ] No configuration in which a module's gates are enabled and silently not running
- [ ] `ADR-capability-modules` amended, including whether #1427's criterion applies here and why

## References

- #1488 (the guardrails module), #1427 (`checks` decision + the criterion), #885 (`DEVKIT_MODULES`), #883 (the consumer hooks surface)
- `flake.nix` — `hooksEnabled`, `hooksConfigInstall`, the git-hooks.nix `imports` list
- `nix/hooks.nix` — the `yaml`/`check`/`consumer` triple and its drift gate
- `gerchowl/filesender` — the only consumer, on the committed surface, 16 hand-wired gate entries

Refs: #1488

---

# [Comment #1]() by [gerchowl]()

_Posted on August 13, 2026 at 09:19 AM_

## Consolidation — and my v2 `hooks` proposal should be withdrawn

Four independent reviews: prek/pre-commit capability research (factual), a scaffolding/codegen architect, a Nix module-system specialist, and a DX/failure-mode reviewer. Two of them independently reached the same structural conclusion, and a third reframed the question in a way I think is correct.

### Established as fact (with sources)

The capability research settles several options outright:

- **No `include` / `extends` / `inherit`, in either tool.** pre-commit refused it explicitly — asottile, [#1203](https://github.com/pre-commit/pre-commit/issues/1203): *"multiple configs / inclusion is not going to be implemented, sorry"*, reaffirmed on [#3422](https://github.com/pre-commit/pre-commit/issues/3422) in 2025. prek has no such key; [prek#1238](https://github.com/j178/prek/issues/1238) is on the roadmap and explicitly unscheduled.
- **One `repo:` stanza cannot pull a whole hook set.** Every hook id must be enumerated by the consumer. `.pre-commit-hooks.yaml` only advertises; it does not bulk-import. True for git repos, local paths, `repo: local` and prek's `repo: builtin`.
- **No env-var injection** of a config or extra hooks. `PREK_SKIP`/`SKIP` only subtract.
- **`-c/--config` is single-valued**, not repeatable.
- **Workspace mode exists but does not solve this.** prek recursively discovers `.pre-commit-config.yaml` files in subdirectories and runs them all in one `prek run` — but *"each project can only see and process files within its own directory tree"*. Repo-wide gates cannot live in a subproject. **Option E is dead.**

Useful and previously unknown: prek has **`--group` / `--require-group`**, a prek-only mechanism for selecting a tagged subset of hooks in a hand-owned config.

The Nix specialist reached the same conclusion from the other side: **the committed surface is genuinely closed to invisible flake-side contribution.** So **option D (merge the consumer's YAML) is the only remaining way to reach it, and it mangles comments, ordering and wrappers.**

### A concrete bug in my draft, verified

The Nix reviewer flagged that **list-typed options do not concatenate across priority tiers — the higher-priority list replaces**. I reproduced it rather than take it on trust:

```nix
{ config.excludes = lib.mkOverride 500 [ "module-added" ]; }   # module tier
{ config.excludes = [ "consumer-added" ]; }                    # consumer, plain
# => [ "consumer-added" ]
```

The module's exclude vanishes silently. My three-tier 999/500/100 scheme would have shipped that. Moot if the flake does not carry hooks at all, which is where this lands.

### The layer question — scaffold, and the argument is better than mine

I had been asking "which layer writes the file". The architect's correction: that is a symptom, and the real test is **who consumes it, and when**:

> `.pre-commit-config.yaml` is read by the runner from a bare git working tree, by **CI containers that never enter `nix develop`**, and by human reviewers scanning a PR diff.

The CI point is decisive and I had not weighted it. Two further arguments I had not made:

- **Update semantics.** A gate set that mutates under a consumer on `nix develop` is a supply-chain vector against your own repos. pre-commit's native model is a *pinned, reviewable manifest* — `rev:` per hook, changed by explicit PR. Scaffold rendering matches that; flake generation breaks it.
- **Migration.** Scaffold ownership needs **zero** migration. Flake ownership forces every consumer to delete a hand-edited committed file and adopt a codepath none of them use.

### The reframe — and I think it is right

The DX reviewer rejected all four options on the grounds that they attack the wrong target:

> All four try to make the *config* correct. The eight prior failures were about *execution*, not config.

That is verifiable against the record. Of the eight logged instances in `gerchowl/filesender`, at least four — wrong YAML indent, commands absent from `PATH`, a recipe running one of two stages, `nix flake check` in no workflow — were **"listed, didn't run."** A check that asserts *presence in YAML* catches none of them. Which also sinks option C on its own terms.

Their proposal: **each gate ships a canary self-test.** CI plants a known-bad fixture, asserts the gate rejects it. "Protected" stops meaning "the entry is in the file" and starts meaning **"the gate rejected a known-bad input in the last CI run"** — which is unfakeable, and which no amount of config drift can counterfeit.

This is devkit's existing fixture doctrine moved one layer out. devkit-side fixtures prove a gate *works*; a consumer-side canary proves it *is wired and executing here*. Those are different claims and only the second addresses the failures.

### Verdict

**Delivery: scaffold (B). Assurance: canary self-test in CI. Contract: unchanged.**

The two winning reviews are complementary rather than competing, and each answers the other's objection:

- DX's objection to B — *"the installer is not re-run, so the committed config drifts from module intent silently"* — is answered by the canary: the selftest fails when a gate is not running, whatever the reason.
- The architect's objection to flake-side delivery — *CI never enters the shell* — is answered by scaffold delivery.

**Consequence: withdraw the v2 `hooks` contract from #1488.** The reasoning there applied #1427's criterion at the wrong layer. `checks` and `hooks` are not two answers to the same question; `checks` is a flake-layer artifact and `hooks` is a scaffold-layer one, and the criterion only ever applied to things competing for the shell-composition contract. The capability-module contract stays v1 for this — no fourth field.

The `guardrails` module therefore contributes **`packages` only** (the gate executables on PATH), which the v1 contract already allows and which needs no contract change at all. Hook *entries* are rendered by the installer from `DEVKIT_MODULES`, and their execution is proven by the canary workflow.

`--group` is the affordance that makes this tidy: scaffold-rendered module hooks carry a group tag, so they are selectable (`prek run --group guardrails`) and the canary can target exactly them.

### Revised scope for #1488

- [ ] `guardrails` module: `packages` only, v1 contract, no ADR contract change
- [ ] Installer renders module hook entries into the committed config from `DEVKIT_MODULES`, group-tagged
- [ ] **Canary workflow**: per active gate, plant a known-bad fixture, assert non-zero exit. New gates auto-enrol from the module list
- [ ] Reconcile `DEVKIT_MODULES` with the flake's `modules` — one source, the other derived or asserted equal, per the architect's warning that two hand-edited lists diverge within a quarter
- [ ] ADR records: hooks are a scaffold concern; why #1427's criterion does not apply across layers

Refs: #1488


---

# [Comment #2]() by [c-vigo]()

_Posted on August 13, 2026 at 11:26 AM_

Decided and shipped in #1495: `.pre-commit-config.yaml` stays a scaffold concern. A capability module contributes gates by putting them on PATH (v1 contract, no new field) — the config is read from a bare working tree and by CI containers that never enter `nix develop`, and neither prek nor pre-commit supports config inclusion. Ships in 1.9.0.

