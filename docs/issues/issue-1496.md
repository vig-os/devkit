---
type: issue
state: open
created: 2026-08-13T10:18:37Z
updated: 2026-10-01T14:59:45Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1496
comments: 1
labels: feature, priority:medium, area:workspace, effort:large, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:27.227Z
---

# [Issue 1496]: [Rust pack: L1/L4/L7 never shipped — the pack cannot be adopted cold](https://github.com/vig-os/devkit/issues/1496)

Found auditing what the Rust pack (#1400, #1429) actually delivered against its design, `docs/designs/0001-rust-language-pack.md` §3.1.

## What shipped

| layer | | |
|---|---|---|
| L1 scaffold statics (`assets/lang.d/rust/`) | **not shipped** | no `assets/lang.d/` at all |
| L2 capability module | shipped | `nix/modules/rust.nix` |
| L3 `lib.mkRustProject` | shipped | `nix/mk-rust-project.nix` |
| L4 justfile seeding | **not shipped** | `assets/justfile.d/` has only `node.justfile.project`; the only seeder is `seed_node_justfile_project` |
| L5 Cargo policy | not shipped as a template | ships via L7, which does not exist |
| L6 release | partial / blocked | the `release-extension.yml` seam is scaffolded but is a default no-op |
| L7 `nix flake init -t #rust` | **not shipped** | `templates.{personal,python}` only |

## Why this matters more than a checklist

**The design said to build L7 first**, and gave the reason:

> crane has ~30 lib primitives and 14 templates; the templates are what people adopt. A consumer who must compose primitives to get started will copy-paste instead.

That ordering got inverted: L2/L3 landed, the entry point did not.

**Consequence: the pack has never been adopted cold.** A new Rust consumer today gets the check suite, the perf ratchet and the mold wiring — and hand-writes every file that *triggers* them: `flake.nix` (a PRESERVE_FILE), `rust-toolchain.toml`, `Cargo.toml` + `[workspace.lints]`, `rustfmt.toml`, `clippy.toml`, `deny.toml`, `about.toml`/`about.hbs`, `.cargo/config.toml` and `justfile.project`.

That last one has teeth. The scaffold seeds **Python** recipes guarded on `[ -f pyproject.toml ]`, so on a Rust repo `just lint` and `just test` silently no-op and CI goes green **without compiling anything** — the exact failure the pack's own design opens with. A consumer who forgets to overwrite `justfile.project` gets a green build of nothing.

`gerchowl/filesender` never hit this because its Rust layer predates the pack — extraction was a move, not an onboarding. `gerchowl/squelch` did hit the cold-start path and reported precisely this.

## Scope

- [ ] **L7 first**: `templates/rust` + `templates.rust` in `flake.nix`, parameterised by tier, matching `#python`
- [ ] L1: `assets/lang.d/rust/` with base `rustfmt.toml`, `clippy.toml`, `deny.toml`, `.cargo/config.toml`, scaffold-once/preserved
- [ ] L4: `assets/justfile.d/rust.justfile.project` + `seed_rust_justfile_project()`, mirroring the node seeding
- [ ] A test that a freshly scaffolded Rust repo's `just test` actually compiles something — the silent-no-op above is the failure to gate against, and it is invisible to inspection

## Pitfall

L1 statics and the `guardrails` module (#1488) both want to own `deny.toml` and the clippy/rustfmt hook entries. That ownership question is already open on #1400 and should be settled before L1 ships, not after.

Refs: #1400

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 02:59 PM_

The consumer-matrix `rust` cell (PR #1807, `scripts/consumer-matrix/render-cell.sh`) is the acceptance test for this issue. It scaffolds a zero-dependency Rust hello world (`tests/fixtures/consumer/rust/`) and requires `just test` to actually run its `#[test]`. Today it fails with the silent no-op this issue describes ("`just test` exited 0 but the rust fixture suite never ran"), so the cell carries a strict expected-fail marker: `EXPECTED_FAIL[rust]="test #1496"` in that script. Once Rust consumers get a real test recipe, the cell starts passing and CI fails on purpose ("rust now passes — remove the #1496 expected-fail marker"). **The PR that fixes this issue must remove that marker.**

