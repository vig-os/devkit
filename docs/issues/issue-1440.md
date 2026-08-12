---
type: issue
state: open
created: 2026-08-12T07:54:01Z
updated: 2026-08-12T09:48:24Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1440
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:41.895Z
---

# [Issue 1440]: [Decision: should crane + fenix be devkit inputs, or move out of the shared lock?](https://github.com/vig-os/devkit/issues/1440)

Split out of #1429 (review-ask #1) so it can be decided on its own evidence rather than inside a feature PR.

## The decision

#1429 adds `crane` and `fenix` as devkit flake inputs, so `lib.mkRustProject` can resolve a repo's `rust-toolchain.toml`. **Every consumer inherits them, including the Python-only ones that will never build a line of Rust.**

Keep them as devkit inputs, or move them out?

## What I measured (aarch64-darwin, Nix 2.34.7+1, `lazy-trees` not available)

**Lock nodes:** 12 → 15. New: `crane`, `fenix`, `fenix/rust-analyzer-src`. (`fenix/nixpkgs` follows devkit's.)

**Fetched source size:**

| input | size |
|---|---|
| `crane` | 3.6 MB |
| `fenix` | 1.4 MB |
| `fenix/rust-analyzer-src` | **28 MB** |
| **total** | **~33 MB** |

**85% of the cost is one transitive input devkit never chose.** `rust-analyzer-src` is fenix's dependency; overriding `fenix` makes it vanish from the lock entirely.

**Eval is lazy — verified, not assumed.** Overriding `fenix` with an empty stub flake and evaluating the zero-module dev shell:

```
$ nix eval --raw .#devShells.aarch64-darwin.default.drvPath \
    --override-input fenix path:/tmp/emptyflake
/nix/store/6p89zysghriiyq3dg84q5c6n7fnbwsha-nix-shell.drv     # unchanged
```

A non-Rust consumer's dev shell evaluates fine against a fenix that isn't there. So the cost is **not** eval-time. It is:

1. **Lock/fetch time** — `nix flake lock` / `nix flake update` must fetch each input to compute its narHash. ~33 MB, once per cold cache.
2. **Three extra lock nodes** in every downstream `flake.lock`, forever, showing up in every dependency review, SBOM and audit.
3. **Supply-chain surface** — a Python repo's lock now pins a Rust LSP source tree. Nobody in that repo has a reason to review it.

I have not measured: CI cold-cache cost per run, `nix flake show` / `metadata` / `archive` / `check` (which may not be as lazy as `eval`), or the double-fenix case where a Rust consumer pins its own without `follows`.

## Why they were added

devkit is the org's toolchain SSoT. The alternative — every Rust repo pinning its own fenix — is per-repo drift on exactly the axis devkit exists to hold still. `mkRustProject` already accepts `crane`/`fenix` overrides, so the inputs can move out without a consumer-visible API change.

## Options

- **(A) Keep as devkit inputs.** SSoT holds; every consumer pays ~33 MB and 3 lock nodes.
- **(B) Consumer-passed.** `mkRustProject { crane, fenix, ... }` required. Zero cost for non-Rust consumers; each Rust repo pins its own, which is the drift devkit exists to prevent — though devkit could still *document* the pin.
- **(C) Sub-flake in the same repo** (`nix/rust/flake.nix`), consumed as `github:vig-os/devkit?dir=nix/rust`. Rust consumers add one input; non-Rust consumers pay nothing; the pin stays in devkit's repo, versioned with it.
- **(D) Keep fenix, drop the 28 MB.** Get the toolchain from `rust-overlay` or nixpkgs' Rust instead, or find whether `rust-analyzer-src` can be excluded. Attacks the actual cost driver rather than the principle.
- **(E) Keep as inputs, revisit if measured CI cost bites.** Status quo with a tripwire.

## Pitfalls

- **The SSoT argument may be weaker than it sounds.** devkit does not pin the *Rust version* — that comes from each repo's `rust-toolchain.toml`. It pins the *resolver*. How much drift does pinning the resolver actually prevent?
- **Symmetry check:** devkit already carries `home-manager`, `process-compose-flake` and `services-flake` for capabilities most consumers never use. If those were acceptable, what makes these different — and if the answer is "size", that is an argument about `rust-analyzer-src` specifically, i.e. option (D).
- **(C) may be worse than it looks:** a second flake means a second lock to keep in step, and cross-flake `follows` on nixpkgs gets awkward.
- **(B) trades a measurable cost for an unmeasurable one.** Drift is real but slow and invisible; 33 MB is visible and immediate. Easy to over-weight the one you can see.
- **Reversibility is asymmetric.** Adding inputs later is a lock update. Removing them later breaks any consumer that came to rely on `devkit.inputs.fenix`.

## Acceptance

- [ ] A decision with a stated reason, recorded where the next person will find it
- [ ] If (A): the tripwire that would reverse it, written down
- [ ] If not (A): #1429 updated, and `mkRustProject`'s override path documented as the supported one
- [ ] The `rust-analyzer-src` 28 MB addressed on its own terms — it is 85% of the cost under every option that keeps fenix

## References

- #1429 (the PR), #1400 (the pack), #1427 (the contract decision)
- `nix/mk-rust-project.nix` — `crane`/`fenix` are already parameters, so (B)/(C) need no API change
- First consumer: `gerchowl/filesender@chore/adopt-devkit`

Refs: #1429

---

# [Comment #1]() by [gerchowl]()

_Posted on August 12, 2026 at 08:12 AM_

## New measurements — one of them corrects the issue body, one kills 85% of the cost

Four independent reviews (Nix internals / Nix packaging patterns / dependency governance / Python-only consumer). Two of them prompted experiments that changed the facts.

### 1. Which operations actually fetch an unused input

The internals reviewer was right that my original test was under-scoped: an unchanged `drvPath` proves the *evaluator* never forced the input, not that the tree was never fetched — fetching happens in the flake-input-resolution layer. Their prior was that `nix flake check` / `show` would fetch regardless.

Proper experiment: a scratch flake with a 20.8 MB `flake = false` input that **no output references**. Lock it, delete the input's store path, run each operation, check whether the path comes back.

| operation | unused input fetched? |
|---|---|
| `nix eval` | no |
| `nix flake show` | no |
| `nix flake check` | **no** |
| `nix flake metadata` | no |
| `nix develop` | no |
| `nix build` | no |
| `nix flake archive` | **yes** |
| `nix flake lock` / `update` (re-lock) | **yes** — narHash must be computed |

So on `Nix 2.34.7+1`, `experimental-features = fetch-tree flakes nix-command`, **no `lazy-trees`**: laziness holds for every operation a consumer runs day to day. The recurring cost is `nix flake update` (each Renovate-style bump) and `nix flake archive`. Everything else is zero.

Caveat I cannot close from here: this is one Nix build on one platform. Upstream CppNix without `fetch-tree`, or an older CI Nix, may differ. Anyone relying on this should re-run the experiment on the CI image.

### 2. `rust-analyzer-src` can be followed away for free — 33 MB → ~5 MB

```nix
fenix.inputs.rust-analyzer-src.follows = "nixpkgs";
```

Lock nodes drop from 15 to 13; the 28 MB node disappears entirely.

The internals reviewer predicted this breaks `fenix.packages.*.rust-analyzer`. **It does not break the case that matters here**, and I built it to check rather than reasoning about it:

```
$ nix build .#default        # fromToolchainFile against filesender's rust-toolchain.toml
$ ls result/bin
cargo cargo-clippy cargo-fmt clippy-driver rust-analyzer rust-gdb
rust-gdbgui rust-lldb rustc rustdoc rustfmt
```

`rust-analyzer` is still there. `fromToolchainFile` takes components from the **release channel manifest**, not from `rust-analyzer-src` — that input only feeds fenix's *nightly* rust-analyzer derivation, which the pack never touches. **85% of the cost is removable with one line and no functional loss.** This is uncontested across all four reviews and should land regardless of how the main question is decided.

## Where the reviews land

**Split 2–2 — and the split is not about the same thing.**

**Ship it as-is** (internals, consumer advocate) — both argued from **cost**. The Python-only maintainer was blunt: *"in none of my real workflows does this register"*, ranking their asks as changelog note first, shed the 28 MB second, *"don't do it"* last — *"I'd be a jerk to block your PR over principle when the concrete cost to me is ~zero."*

**Push it out** (governance, packaging patterns) — both argued from **convention and trajectory**, not cost.

The packaging reviewer surveyed real `flake.nix` files rather than recalling them, and the result is one-sided:

| flake | language toolchain inputs |
|---|---|
| `cachix/git-hooks.nix` | none — `nixpkgs` + `flake-compat`, despite hooks for Rust/Go/Haskell/JS |
| `numtide/treefmt-nix` | none |
| `ipetkov/crane` | **`inputs = { };`** — literally empty |
| `oxalica/rust-overlay` | `nixpkgs` only |
| `nix-community/dream2nix` | none, despite JS/Python/Rust support |

> Library-flakes that serve many languages carry zero language toolchain inputs. Only leaf/single-language flakes carry them.

`git-hooks.nix` is the sharpest precedent: devkit **already consumes it**, it supports many languages' hooks, and it carries no toolchains. Also: `?dir=` sub-flakes (option C) have **zero adoption** in the survey and known re-locking problems; `builtins.getFlake` (option E) is an anti-pattern. The flake-parts ecosystem's answer is separate repos — `haskell-flake`, `rust-flake` — and `rust-flake` *does* declare crane, which is fine precisely because everyone depending on it is a Rust consumer.

The governance reviewer independently landed in the same place and supplied the rule: **devkit inputs may add capabilities, but must not carry language-specific toolchain payloads** — which keeps the existing `home-manager` / `process-compose-flake` / `services-flake` precedents and excludes these. Plus the year-three point: *"The threshold isn't at pack 5 — it's at pack 2. The moment you set the precedent, the next three requests cite it and you lose the ability to say no on principle."*

## Consolidated recommendation: (B), consumer-passed

**Better measurements cannot settle this, and that is the finding.** I sharpened the cost number twice — first by testing laziness properly, then by removing 85% of the bytes — and neither touched the case against. The two reviewers who said ship-it were answering *"does this hurt?"*; the two who said push-it-out were answering *"is this the right shape, and what does it license next?"* A more precise cost figure cannot rebut an argument that was never about cost.

On the merits of the shape:

- **The SSoT justification is weaker than I claimed when I wrote it.** devkit would pin the *resolver*, not the compiler — the compiler comes from each repo's own `rust-toolchain.toml`. I used "prevents per-repo drift" to justify this, and it prevents less drift than that phrasing implies.
- **The ecosystem convention is unanimous and directly comparable.**
- **Reversal is free right now and never again.** One consumer exists (`gerchowl/filesender`), nothing depends on `devkit.inputs.fenix` being reachable, and `mkRustProject` already takes `crane`/`fenix` as parameters — so (B) needs **no API change**, only moving where they are supplied.

Mitigations for the drift risk, neither requiring a signature change:

1. `lib.rust.recommendedInputs` — a curated, locked snippet Rust consumers copy, versioned in devkit and documented. Drift becomes visible and reviewable instead of implicit.
2. `mkRustProject` asserts `fenix ? packages` and `crane ? mkLib`, failing with a pointer to that snippet — the same fail-loud discipline #1427 applied to the module.

If drift ever does bite, promote the snippet to a sibling flake (`vig-os/devkit-rust`), which is what the flake-parts ecosystem does. Do **not** use `?dir=`.

And land the `rust-analyzer-src` follows either way — it is free, and whoever ends up carrying fenix should not carry 28 MB of nightly LSP source to get a component the channel manifest already provides.

Refs: #1429


---

# [Comment #2]() by [gerchowl]()

_Posted on August 12, 2026 at 09:48 AM_

**Partial landing.** The `rust-analyzer-src` follows shipped in #1429 ([e9349eb](https://github.com/vig-os/devkit/commit/e9349eb7)) — lock nodes 15 → 14, fetched source ~33 MB → ~5 MB, `rust-analyzer` still present in the built toolchain. That was the one point all four reviews agreed on regardless of the outcome here.

**The main question stays open**, deliberately. The consolidated recommendation above is to move `crane`/`fenix` out to consumers — which reverses my own original call — but the case for it rests on ecosystem convention and the year-three trajectory, not on cost. That makes it a convention decision for the ADR owner rather than something to land inside a feature PR.

Whoever picks this up: the two measurements in the comment above are the ones that matter, and the second one shrank the cost side of the argument by 85%. Neither changed the case against.

