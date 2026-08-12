---
type: issue
state: open
created: 2026-08-11T22:40:09Z
updated: 2026-08-12T00:02:46Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1427
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:04.413Z
---

# [Issue 1427]: [Decision: where do a capability module's CHECKS live — lib function or a v2 contract field?](https://github.com/vig-os/devkit/issues/1427)

Blocker for the Rust language pack (#1400). Filing separately because it is a
**contract decision about the module system**, not a Rust question — whatever is
decided applies to `node`, `docs` and every future module.

## Motivation

`ADR-capability-modules` fixes the v1 contract as
`pkgs -> options -> { packages, env, shellHook }`. That is sufficient for
`native` (a compiler on PATH) and `node` (a toolchain).

It is **not** sufficient for a language pack whose value is largely *checks*.
A Rust pack contributes `clippy`, `rustfmt`, `nextest`, doctests, `cargo-deny`
and a crane fileset — all flake `checks`, none expressible as a shell
contribution. A consumer who writes `modules = [ "rust" ]` and nothing else
would get a toolchain **and no checks**, i.e. a repo that looks equipped and
gates nothing.

That failure mode is not hypothetical. In the first consumer
(`gerchowl/filesender`) the same class of error occurred five separate times in
one branch — config referenced but absent, or wired but never executed — and in
the worst instance the entire gate suite had never run in CI. See
docs/GOAL.md §6 there. A module that silently supplies no checks is the same
shape.

## What already exists

- `nix/modules/default.nix` — registry; `rust` is named as an ask-gated candidate
- `nix/modules/node.nix` — **precedent**: v1's ADR explicitly excluded per-module
  option attrsets, and #1027 added `version` anyway when a consumer needed it.
  The contract has already grown once, for this exact reason.
- `ADR-capability-modules` — records hooks contribution as an *open design
  question* deferred to #883's wave, with the stated intent that the
  `mkProjectShell` diff region stay small so `hooks` lands beside `modules`.
- The **zero-module invariant**: `modules = [ ]` must remain byte-identical
  (asserted via `drvPath` + `tests/test_flake_devshell.py`). Any option here
  must preserve it.

## The options

**A. `vigos.lib.mkRustProject` — a lib function, no contract change.**
Module stays toolchain-only; checks come from a separate lib call a consumer
adds to its own flake. Ships without touching module machinery.
*Cost:* two opt-ins for one capability, and the module-only path silently
under-delivers.

**B. Extend the contract so a module can contribute `checks`.**
One opt-in. Applies uniformly to future modules.
*Cost:* modules currently contribute to a **shell**; checks are **flake
outputs** — arguably a category difference, not just a missing field. Also
touches shared machinery and the byte-identical invariant.

**C. Both, with the template as the seam.**
Keep the categories separate (A), but have `nix flake init -t …#rust` wire the
module *and* the lib, so a consumer following the documented path never hits
the gap. The gap survives only for someone hand-adding `modules = [ "rust" ]`.

## Pitfalls

- **Category error.** `packages`/`env`/`shellHook` are all shell inputs.
  `checks` are flake outputs, per-system, and evaluated by `nix flake check`,
  not by entering a shell. Adding them to the same attrset may be conflating
  two lifecycles.
- **The zero-module invariant.** Any change must keep `modules = [ ]`
  byte-identical, or the parity suite breaks.
- **Silent under-delivery is worse than a hard error.** If A is chosen, a
  module-only adopter should probably *fail loudly* rather than quietly provide
  no checks.
- **Precedent cuts both ways.** #1027 shows the contract can grow — but growing
  it per-consumer is how a small seam becomes a large one.
- **`checks` need `src`.** Unlike `packages`, a check derivation needs the
  consumer's source and its fileset. A module has no access to that, so the
  contract would need a source argument too — this may be the real reason
  checks do not fit the current shape.

## Scope

- P0 — decide A / B / C, and record it as an ADR amendment
- P0 — if A or C: define what a module-only adopter experiences (silent, warn, throw)
- P1 — if B: specify how `src` reaches a module, and how the zero-module invariant holds
- P1 — apply the decision to #1400's Rust pack

## Acceptance criteria

- [ ] Decision recorded, with the losing options and why
- [ ] `ADR-capability-modules` amended or superseded
- [ ] #1400 unblocked with a stated shape for L2/L3

## References

- #1400 — Rust language pack, and the guardrails reconciliation
- #883 — the hooks-contribution wave the v1 ADR defers to
- #1027 — per-module options; the precedent for growing the contract
- `docs/rfcs/ADR-capability-modules.md`
---

# [Comment #1]() by [gerchowl]()

_Posted on August 12, 2026 at 12:01 AM_

## Resolution — **A + D + assert**: library composition, no contract change, fail-loud backstop

Three independent reviews (systems architect / devkit maintainer / DX-footgun), each given the same background and no shared conversation. Verdict below is the consolidation, not a vote count.

### Where all three agree

- **The silent gap disqualifies bare Option A.** Nobody accepted "documented" as mitigation. A module-only adopter getting a toolchain and no checks is precisely the failure this pack exists to prevent.
- **`src` is the crux.** A v1 module gets `pkgs -> options`. Checks need the project's source tree, which is consumer-owned project shape — neither ambient in the module nor derivable from options. That asymmetry, not ergonomics, is why checks don't fit the shell-composition contract.
- **The template (Option C) is not a fix.** It covers greenfield only — not hand-edits, not copy-paste, not existing repos, not agent-generated flakes.

### Where they split

**2 for the A-family, 1 for B.** The reasoning matters more than the count.

**Systems architect → A, executed as library composition (call it D).** Checks are a *category error* against the existing contract: `packages` / `env` / `shellHook` are monoidal folds into one derivation; `checks` is a namespaced map of independent peer derivations on a different lifecycle (`nix flake check`, not `nix develop`). The sharpest test offered:

> If a field can be added to the shell composition contract without touching shell composition, it isn't part of that contract.

B *can* preserve the zero-module invariant — trivially, by having `checks` not participate in shell composition at all. That's the tell.

Reframe: *you don't have a module problem, you have a `mkProject` you haven't named yet.*

**Maintainer → A+ (guard + template), not B.** A `checks` field would be Rust-shaped, added for one repo, dead code for `native` / `node` / `docs` — "the definition of a seam you pay for forever." And it inverts the `node.version` precedent I filed this issue with:

> The `node.version` precedent is a warning, not a licence.

The ADR excluded per-module options; someone shipped one anyway. **The actual bug is that the contract drifted without its governing document being updated.** Fix that before compounding it. Also flagged that the consumer evidence is weak — one repo where the tooling is the product, 2:1 tooling-to-product LOC.

**DX/footgun → B.** Because this org has proven, five times in one branch, that it does not detect what it configured:

> The wrong thing must be impossible, not merely detectable.

Calls A "your dominant failure mode repackaged as an API."

### A hole in the B argument, surfaced by consolidation

B's case rests on *"there is no second call to forget."* That does not survive scrutiny. **Flake outputs are consumer-assigned by construction.** Under B, `modules = [ "rust" ]` still cannot make `checks.${system}` appear in the consumer's flake unless `mkProjectShell`'s *own* return shape changes too — which is a larger contract break than the one being debated.

The footgun review half-concedes this: its fallback is to emit a check named `rust-checks-not-wired`, which the consumer must wire up in order to see. Circular.

**So "impossible" is not on offer from any option.** What is on offer: one source instead of two, plus loud detection.

### Decision

Combine the architect's mechanism with the maintainer's backstop. Neither review proposed this; it dominates all three.

1. **Library composition (D).** `vigos.lib.mkRustProject { pkgs, src, ... }` internally calls `mkProjectShell` with a private toolchain module and returns `{ devShell, checks, packages }`. One consumer call. `checks` sits visibly beside `devShell` in the returned attrset, so omitting it is a visible omission rather than an unknown-unknown. **No contract change.**
2. **Eval-time assert.** `mkProjectShell` throws if `modules` contains `"rust"` without the sentinel `mkRustProject` sets. This catches the residual case — someone hand-edits a flake, wires `devShell`, drops `checks` — at *evaluation*, before CI can ever go green. Cost: one module-local assertion, not a contract field. This is the maintainer's `checksAcknowledged` idea.
3. **The footgun review's error text**, reused verbatim as the assert's message, including its escape hatch: `modules = [ "rust-toolchain-only" ]`. The hatch matters — without one, the assert gets silenced by deleting the module, which is strictly worse.

### Not doing (and the bar for revisiting)

The contract does **not** grow `checks` now. Per the maintainer review, revisit only when **a second capability module independently needs to contribute checks** — i.e. the need is demonstrated by a non-Rust consumer, not argued from one repo. Until then B is a seam bought on speculation.

### Precondition — fix the ungoverned drift first

`node.version` shipped an option the capability-module ADR explicitly excluded, and the ADR was never updated. Either revert it or promote it into the ADR. Otherwise devkit has a governing document that no longer governs, and every future consumer inherits exactly the precedent argument this issue was opened with.

/cc @c-vigo — this is your ADR; the decision above is a recommendation pending your sign-off on the contract question and on the `node.version` reconciliation.


---

# [Comment #2]() by [gerchowl]()

_Posted on August 12, 2026 at 12:02 AM_

### Correction — the `node.version` precondition above is wrong, withdraw it

I filed this issue (and the consolidation above) on the premise that per-module options were *excluded* by `ADR-capability-modules` and that `node.version` shipped anyway, leaving the contract ungoverned. I have now read the ADR properly. That premise is false.

The ADR lists per-module option attrsets under "Explicitly **not** in v1" **but immediately provides the sanctioned path**:

> ## Migration path to per-module options
> When a module needs configuration (e.g. Geant4 datasets), `modules` also accepts an attrset entry `{ name = "geant4"; datasets = [ … ]; }` alongside plain strings — additive, no break for the string form. **Not built until the first module needs it.**

`node.version` (#1027) is that path executed exactly as written — and `nix/modules/node.nix` says so in its own header comment. Nothing drifted. **There is no precondition to clear, and the maintainer review's "warning, not a licence" framing rests on my bad summary, not on the record.**

Two things this actually changes:

1. **The precedent argument I opened with is stronger, not weaker.** The ADR's pattern is: name the extension, defer it, build it when a real consumer asks. That is a *governed* deferral, and it is the pattern this issue should follow.
2. **`checks` has no such recorded deferral.** Hooks-contribution does ("open design question, recorded here for #883's wave"); per-module options did; `checks` is not mentioned anywhere in the ADR. So extending the contract for it would be a genuinely new decision rather than executing a documented plan — which *supports* the A+D+assert verdict, just for a different reason than I gave.

Also worth recording, since it settles the standing of this work: `rust` is already an **ask-gated candidate** in the ADR —

> **Ask-gated candidates (named, not shipped — YAGNI):** `geant4`, **`rust`**, `fortran`/`f2py`, `root`. Each ships with its own devshell smoke check the release it lands.

`gerchowl/filesender` is that ask. The verdict stands; the reasoning is amended.


