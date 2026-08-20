---
type: issue
state: open
created: 2026-08-14T17:20:34Z
updated: 2026-08-15T00:34:14Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1523
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-15T02:57:58.509Z
---

# [Issue 1523]: [Org stack matrix: one dated, definitive answer per capability × archetype — so projects and agents stop re-rolling](https://github.com/vig-os/devkit/issues/1523)

Raised by a consumer: *"any layout or requirement should get a definite answer for what is the current main stack + the individuals, to not rely on agent LLM probability fever."*

## The problem, concretely

`gerchowl/filesender`'s ADR already decided the dataframe question:

> **DataFrame default: `polars` 0.55.2 (MIT).** `datafusion` is CONSIDER, not a co-default — adopting it means shipping **two Arrow implementations**, because `polars-arrow` is a hard fork of arrow2 and arrow-rs support was removed in polars 0.44, so interchange is FFI-only. `duckdb` is CONSIDER for ad-hoc. Lockstep warning: arrow/parquet/datafusion move as one release train.

That analysis is good, it is verified (2026-08, second pass), and it is **unfindable** — 80 lines inside a 1000-line ADR titled "A Rust language pack for devkit", in a consumer repo. Multiple projects have independently rediscovered polars/duckdb. They will keep doing it.

The failure is not that the answer is wrong. It is that a decided question presents itself as an open one, so every new project and **every agent invocation re-rolls the dice.** A model asked "which dataframe crate" will produce a *plausible* answer every time, and plausible-but-different across three repos is how an org ends up with three stacks, each defensible in isolation.

Worth naming the self-referential risk: much of that ADR was produced with agent assistance. The stochastic-choice problem this would fix is the one that produced it.

## What this is

**A capability × archetype matrix, org-wide, across languages.** Not a Rust concern.

- **capability** — dataframes, columnar storage, CLI parsing, HTTP client, MCP SDK, TUI, errors, logging, serialization, async runtime, client persistence, collaboration, code editor, terminal emulator, …
- **archetype** — `lib`, `cli`, `mcp`, `service`, `data`, `web`, `ffi`, …

Most cells are archetype-independent (`serde` everywhere). A few genuinely vary — `thiserror` for a library, `anyhow`/`eyre` for a binary. **That variance is exactly why it is a matrix rather than a flat "recommended crates" list**, and it is why "tiers" was the wrong word: this repo is `cli` AND `mcp` AND `lib` simultaneously. A ladder cannot express that; a matrix can, by occupying several columns and resolving conflicts explicitly.

## Status vocabulary — four, not three

`DEFAULT` · `CONSIDER` · `REJECTED` · **`UNASSESSED`**

The fourth is the one that keeps it honest. "We have not looked at this" must be distinguishable from "we looked and said no", or the gaps become invisible and get filled by whoever asks an LLM first.

Every row carries **verified-on** and **verified-how**. A row without a verification date is a guess wearing a decision's clothes. Precedent: the ADR's §4 records that its own second pass *corrected* earlier claims, including one ("pick datafusion or polars, never both") that was simply too strong.

## The column that is easy to forget

**Build-graph consequence.** For the storage cells this is most of the value:

- `hdf5-metno` needs `buildInputs = [ pkgs.hdf5 ]` + `HDF5_DIR`, and **must not** use the `static` feature — it invokes CMake to fetch and build libhdf5 at build time and breaks hermeticity
- `zarrs` default features build `blosc-src` from bundled C via CMake; use `default-features = false` plus `gzip`/`zstd`

That is not crate selection, it is build-graph consequence, and a plain "recommended crates" list drops exactly that half. It is also the half that costs an afternoon to rediscover. Compare the 125 MB of `cmake` just removed from a consumer, justified by a comment naming a crate `cargo tree` proves was never in its graph.

## Machine-readable, with the docs derived

The registry is the source; the published table is **generated** from it.

This needs no new machinery: `guardrails-derived-docs` already exists, ships in the `guardrails` module (#1488), and already re-runs a command and diffs its output against a marked region. So the matrix in the docs cannot drift from the registry — which prose demonstrably cannot manage. The consumer that pioneered it has **ten recorded instances** of documentation asserting something no longer true.

The same registry then feeds tooling — archetype-aware defaults, `cargo-deny` bans on REJECTED crates — as a *second* consumer of one source. **Gating is secondary. The primary product is a findable, dated, definitive answer.**

## What exists today, and where it is trapped

**Rust, verified 2026-08, in the filesender ADR:** the whole `data` and `ffi` tiers (arrow/parquet, polars, datafusion, duckdb, `hdf5-metno` 0.14.0 — "the only credible HDF5 crate in 2026, no successor", `zarrs` 0.23.13, `netcdf` 0.12.1, faer, uom, argmin), plus `cli` (clap + clap_complete + clap_mangen, human-panic), `mcp` (rmcp + schemars), `tui` (ratatui + crossterm; termion disqualified on Windows).

**Frontend, in the same Rust ADR because there was nowhere else to put it:** React + TS strict + Vite 8, **Zustand**, **TanStack Router** (React Router v7's type-safety is framework-mode only), **TanStack Query**, react-hook-form + Zod v4, **LinguiJS**, **Tailwind v4 + shadcn/ui**, `@axe-core`.

That last group is the tell. A full React stack is living inside a document about a Rust language pack because the org has no org-level home for it. devkit's `node` module contributes `nodejs` to the shell and **no guidance at all**.

## Known gaps — UNASSESSED, and deliberately not filled here

- **`vortex`**, `lance` — columnar formats absent from the ADR entirely
- **Client persistence** (IndexedDB and its wrappers), **collaboration** (`yjs` / `automerge`), **code editor** (CodeMirror 6 / Monaco), **terminal emulator** (`xterm.js`)
- Domain formats this org actually handles: DICOM, NIfTI

These are listed rather than answered **on purpose**. Generating a fluent paragraph about CM6 versus Monaco from training data is precisely the failure this issue exists to stop.

**The last four are one coupled cluster, not four cells.** An editor choice constrains the collaboration layer (CM6 and Yjs have first-party bindings; Monaco's story differs), and both constrain persistence. Deciding them independently is how you get a mutually incompatible set. One research pass, not four.

## Scope

- [ ] Registry format + home (devkit, org-level — **not** inside a language pack)
- [ ] Seed ONLY from what is already verified, carrying its verification date forward. Do not re-derive; do not backfill from a model
- [ ] Generate the published matrix via `guardrails-derived-docs` so it cannot drift
- [ ] File the UNASSESSED cells as research tasks, the editor cluster as one
- [ ] Move the frontend rows out of the Rust ADR, leaving a pointer

## Pitfalls

- **A matrix nobody executes is the ADR's own failure mode with more ceremony.** Ship it wired to something — derived docs at minimum — or it becomes a second unfindable document
- **Backfilling UNASSESSED rows with plausible answers destroys the entire value.** The registry's worth is that a `DEFAULT` row means someone checked
- **Staleness is the real threat.** A dated row that is two years old is worse than an absent one, because it carries authority. Needs a review cadence, and `guardrails-stale` already exists for calendar-drifting checks
- **Archetype sprawl.** The ADR defines eleven; §4 marks `runner` as pure first-principles and `tui`/`service` as partial. Seed with the ones that have real consumers — `cli`, `mcp`, `lib`, `data`, `web` — and leave the rest prose

Refs: #1519, #1400

---

# [Comment #1]() by [gerchowl]()

_Posted on August 14, 2026 at 05:44 PM_

## Seeding CONSIDER rows: config layering + secret storage

Two capability clusters, researched rather than asserted. **Both carry measurements or sources**, per the verified-on/verified-how rule.

---

## Capability: config layering (`flag > env > file > default`)

The **precedence order is a principle**, org-wide, not a crate choice. Every layer optional, higher wins. The test for which layer a setting belongs in: *how often does it change, and who changes it?* — never → default; per machine/user → file; per environment → env; per invocation → flag.

| crate | status | note |
|---|---|---|
| `clap` (`env` feature) | **DEFAULT** | `#[arg(long, env = "X")]` gives `flag > env` natively. Already a dependency of any CLI; zero marginal cost |
| `config` (config-rs) | **CONSIDER** | Earns its place at many keys, nested structure, multiple formats, or profiles. **Not** at three flat keys |
| `toml_edit` | **CONSIDER** | Only when you WRITE config back and must preserve comments/formatting (a `config set` subcommand). Wrong instrument for a read-only config |
| `figment` | **UNASSESSED** | The live alternative to config-rs. Not verified — do not pick one over the other without checking |

### Measured cost — the number that should decide it

Adding `config` + `toml_edit` to `gerchowl/filesender` (a CLI with **three** config keys), with the API actually exercised so dead-code elimination cannot hide it:

```
baseline:  2,723,056 bytes
with both: 3,536,000 bytes
delta:     +812,944 bytes  (+30%)
```

**+813 KB and 57 crates for three keys.** That repo's perf ratchet has a 5% tolerance, so this fails the gate by 6×.

The point is not that these crates are bad — it is that **"which config crate" is the wrong first question.** The first question is how many keys and how much structure, and below some threshold the answer is `clap(env)` plus an `Option::or` fold in ten lines with no dependency. The matrix should record that threshold, not just a crate name.

---

## Capability: secret storage (a long-lived API token in a CLI)

Two independent research passes. The empirical one is the more useful.

### What widely-used CLIs actually do

| tool | default | mode | keychain | env |
|---|---|---|---|---|
| `gh` | OS keychain, 0600 file fallback | 0600 | **yes** (opt-out `--insecure-storage`) | `GH_TOKEN` > `GITHUB_TOKEN` |
| `docker` | plaintext base64, helper if configured | not enforced | via helpers (Desktop wires one) | `DOCKER_CONFIG` |
| `cargo` | plaintext TOML | 0600 (PR #13898) | opt-in providers | `CARGO_REGISTRY_TOKEN` |
| `aws` | plaintext INI | **none — 0644 on macOS**, open bug #7369 | none | `AWS_*` |
| `kubectl` | plaintext in kubeconfig | not enforced | none (exec plugin) | `KUBECONFIG` (path only) |
| `rclone`, `atuin` | plaintext | 0600 | none | yes |

**Only `gh` (and Docker Desktop) default to a keychain.** The security-literature answer is not the industry practice: the practice is **a mode-0600 file with an escape hatch to something better**.

### The pattern that IS converging

Docker credential helpers (2016) → kubectl `exec` credential plugins (2018) → cargo credential providers (stable 1.74, 2023) → AWS `credential_process`. All the same shape: **a small subprocess protocol, so the tool does not ship keychain integrations and storage becomes pluggable.** That defers per-platform keychains, MDM, corporate vaults and HSMs to something the user picks. This is the piece worth copying unconditionally.

| crate / practice | status | note |
|---|---|---|
| mode-0600 file, created **with** the mode | **DEFAULT** | `OpenOptions::mode(0o600)` — not `write` then `set_permissions`, which leaves a world-readable window |
| `TOOL_TOKEN` + `TOOL_TOKEN_FILE` env | **DEFAULT** | The `_FILE` variant is rare in CLIs and common in Docker/K8s; cheap, and it stops tokens entering shell history |
| `secrecy` 0.10.3 | **CONSIDER** | Mostly ergonomics over a hand-written redacted `Debug` — but *uniform*: blocks `Debug`/`Display`/`Serialize` by default and makes `Clone` opt-in, so it catches the second-order slip (serde, `{:?}` on the parent struct) |
| `zeroize` 1.9.0 | **CONSIDER** | Guarantees only that the last heap slot is cleared on drop. Explicitly **not**: realloc copies, stack spills, registers, mlock. `secrecy` pulls it in anyway |
| `keyring` 4.1.6 | **CONSIDER, never default** | Repo moved to `open-source-cooperative/keyring-rs`. On headless Linux (SSH, containers, most CI) Secret Service returns an opaque `Err`; `linux-keyutils` works but the **session** keyring evaporates on shell exit. Defaulting to it silently breaks SSH and CI users |
| credential-helper / provider indirection | **CONSIDER (recommended)** | The converging norm above |
| obfuscation that looks like encryption | **REJECTED** | rclone's `obscure` is a documented footgun — worse than plaintext because users believe it |

### Anti-recommendations worth recording

- **Never** a secret as a CLI flag — shell history, `ps`, CI logs
- A raw secret in env is the 12-factor default and the weakest widely-defended option: `/proc/<pid>/environ`, inherited by every child, crash dumps, `docker inspect`, error reporters. The `_FILE` indirection resolves this rather than accepting it
- Do not copy AWS's silent 0644 create, or Docker's base64-without-helper (buys nothing, inflates trust)

**Not verified:** `figment` vs `config-rs`; exhaustive RustSec-clean status for keyring/secrecy/zeroize; whether `keyring` 4.x changed its headless error variant.

Refs: #1519


---

# [Comment #2]() by [gerchowl]()

_Posted on August 15, 2026 at 12:34 AM_

## Measured: crate count is a poor proxy for binary cost

Two dependency additions to the same repo (`gerchowl/filesender`), both measured with the API actually exercised so dead-code elimination cannot hide the cost:

| addition | crates | binary |
|---|---|---|
| `config` + `toml_edit` | +57 (+26%) | **+812,944 bytes (+30%)** |
| `keyring` + `secrecy` | +67 (+30%) | **+74,576 bytes (+4%)** |

**More crates, one eleventh the binary.** `keyring` 4.x fans out into per-platform backend crates that are `cfg`'d out at build time, and `secrecy`/`zeroize` are tiny. `config`'s format parsers and `toml_edit`'s format-preserving document model are all live code.

### Why this matters for the matrix

I have been quoting crate counts as a cost signal throughout #1519 and this issue. That was sloppy: it is a *lock-file* metric, and it correlates with audit surface, build time and supply-chain review load — but **not** with what ships.

So a row's "cost" column needs to say which cost:

- **binary size** — what users download and run
- **crate count** — audit and review surface, `cargo-deny` load, build time
- **build-graph consequence** — native toolchain requirements (the `hdf5-metno` / `zarrs` CMake traps)

They are three different numbers and they do not move together. A registry that records one and implies the others will mislead exactly the person trying to be careful.

### And it validates gating both

`filesender`'s perf ratchet gates binary size AND dependency-graph size, which looked redundant when I wrote it. It is not: this change passed the size metric (+4%, inside a 5% tolerance) and **failed the graph metric (+30%)**. One number would have waved through a 67-crate expansion of the audit surface; the other would have waved through the 813 KB. Catching both required both.

Refs: #1519


