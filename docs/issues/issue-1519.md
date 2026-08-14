---
type: issue
state: open
created: 2026-08-14T15:43:43Z
updated: 2026-08-14T15:43:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1519
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:12.256Z
---

# [Issue 1519]: [Smallest denominator, not the sum: drop speculative defaults, and make the tier matrix executable](https://github.com/vig-os/devkit/issues/1519)

Two related problems, one principle. Raised by a consumer asking why devkit hands every Rust repo things it never asked for.

## The principle

**devkit should be the smallest denominator, not the sum.** It may *carry* modules, suggestions and solutions; it must not bloat every consumer with them.

devkit already implements this correctly in three places, and they are the model:

```nix
deny        = if deny != null then deny else pathExists "${src}/deny.toml"
perfRatchet = ...                          pathExists ".repo/perf-baseline.toml"
toolchain   = ...                          pathExists "rust-toolchain.toml"
```

**Evidence-driven**: no flag, no config, no cost. The consumer's own artifacts elect the capability by existing. Nothing is imposed.

## Part 1 — where it accumulates instead

| default | imposed on | evidence for it |
|---|---|---|
| `buildInputs ++ [ libiconv ]` on Darwin | every Rust consumer | **none** |
| `defaultTools` — nextest, deny, auditable, audit, about, shear | every dev shell | none |
| `auditable ? true` | every build command | a policy choice |
| `linker ? true` → mold | every Linux build | none |

`libiconv` is the clearest: added on folklore, **unfalsifiable** (the build passes either way, so nothing ever reports it unused), and paid by everyone. `gerchowl/filesender` builds and passes all 11 checks without it.

This is the same shape as the 125 MB of `cmake` just removed from that consumer — justified by a comment naming `aws-lc-rs`, a crate `cargo tree -e no-dev` says has never been in its graph — except this one lives in the shared layer, where the cost multiplies.

There is also a plain inconsistency: the `deny` **check** is evidence-driven, but `cargo-deny` the **tool** ships unconditionally. A repo with no `deny.toml` gets the binary and not the check. Same for `cargo-about` / `about.toml`.

### The line worth drawing

"Smallest denominator" cannot mean *nothing by default* — a Rust pack that does not lint unless asked is not a pack.

- **Checks are the product.** `clippy`, `fmt`, `nextest`, `doc`, `doctest` defaulting on is the value proposition. Keep.
- **Build inputs and tools are cost.** Evidence-driven or opt-in. Never speculative.

### Scope

- [ ] Drop `libiconv`. **Do not drop it silently** — replace it with the documented seam: `buildInputs = [ pkgs.libiconv ]` in your own call, added when a build failure demands it. A comment saying "no libiconv, here is how to add one" is worth more than either having it or quietly not having it
- [ ] Align tools with checks: `cargo-deny` when `deny.toml` exists, `cargo-about` when `about.toml` exists
- [ ] Decide `auditable` and `linker` deliberately — genuine policy calls, not oversights
- [ ] State the rule in the ADR so the next default has to justify itself

## Part 2 — the archetype matrix, which is the real answer

"Smallest denominator" and "opinionated defaults" are only in tension if the base has to guess. It does not have to: **the consumer knows what they are building.** A declared archetype selects a documented bundle — minimal base, deliberate opt-in, no guessing.

`docs/designs/0001-rust-language-pack.md` §2 already specifies exactly this. Eleven tiers — `lib`, `cli`, `tui`, `mcp`, `runner`, `data`, `web`, `ffi`, `service`, `gui`, `web-ssr` — and `lib` even carries an escalation ladder:

| rung | consumed by | adds |
|---|---|---|
| L0 | this workspace only | nothing beyond base |
| L1 | other repos (git/path dep) | `missing_docs`, a deliberate API surface, a changelog |
| L2 | crates.io | `rust-version` declared **and verified**, `cargo-semver-checks`, docs.rs metadata |

**None of it is executable.** `mkRustProject` has no `tier` argument. `toolGroups` (`@perf`, `@perf-async`, `@api`) is the only mechanism that exists, and `@api` = semver-checks + expand is the lib bundle by accident rather than by design.

So ~400 lines of prescription that no code reads — written down, believed operative, never executed. The same failure class this pack was built to catch, in the pack's own design document.

### The shape

```nix
rust = mkRustProject { tier = "lib"; rung = "L1"; … };
```

selecting: the tool group, the check defaults, and the lint policy — all documented, all overridable, none imposed on a consumer who does not declare a tier.

### The discipline this needs

**Ship two or three tiers, not eleven.** §4 of the ADR marks `runner` as pure first-principles and `tui`/`service` as partial — three of eleven are unverified by anything. Shipping a mechanism for an unvalidated taxonomy builds on sand, and the capability-module ADR's own YAGNI rule ("candidates are named, not shipped, until a concrete consumer asks") applies to tiers exactly as it applies to modules.

Real consumers today: `cli` and `mcp` (filesender), `lib` (squelch, and filesender-core at L0→L1). Start there. The other eight stay documented candidates until someone asks.

### Acceptance

- [ ] No speculative build input or tool ships to a consumer that did not ask for it or evidence it
- [ ] A declared `tier` selects a bundle that is documented in one place and read by code in one place
- [ ] Tiers ship only with a consumer behind them; the rest stay prose
- [ ] The ADR states the smallest-denominator rule, so the next addition has to argue for itself

Refs: #1400, #1488

