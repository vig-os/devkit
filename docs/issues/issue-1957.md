---
type: issue
state: open
created: 2026-10-29T02:32:35Z
updated: 2026-11-08T14:36:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1957
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-09T09:33:50.258Z
---

# [Issue 1957]: [rust pack: workspace template, layer check, affected-test and timings recipes](https://github.com/vig-os/devkit/issues/1957)

Requested by the cx owner (2026-10-29), from cx v2's engine work. Today the Rust pack (`assets/lang.d/rust/{clippy,deny,rustfmt}.toml`, `nix/mk-rust-project.nix`, `assets/justfile.d/rust.justfile.project`) has lint and format config but no workspace or layering support.

Proposed additions (generic, for any Rust project):

1. **Workspace template.** A flat `crates/*` layout with a virtual manifest at the root, folder name = crate name, `[workspace.package]` / `[workspace.dependencies]` inheritance (per matklad's "Large Rust Workspaces").
2. **Layer check.** A `layers.toml` declaring layers and the allowed dependency direction between workspace crates, e.g.:
   ```toml
   [layers]
   order = ["backend", "storage", "logic", "service", "query"]
   [crates]
   cx-backend = "backend"
   cx-segment = "storage"
   ```
   It is enforced in CI from `cargo metadata`: an upward or same-layer-cycle dependency fails with the offending edge named. Ship it as a tiny xtask or script in the pack.
3. **Affected tests.** A just recipe `test-affected [base]`:
   - map `git diff --name-only <base>...HEAD` to packages via `cargo metadata`;
   - run `cargo nextest run -E 'rdeps(a) | rdeps(b)'`;
   - fall back to the full suite when a changed path is outside every package (root Cargo.toml/lock, flake, scripts, CI);
   - print the selected packages and test count, and treat 0 selected tests as a FAILURE.
4. **Timings.** A just recipe `timings` running `cargo build --timings` plus nextest's slowest tests, to inform split decisions.
5. **Docs.** A short guide on when to split a crate: acyclic and stable dependencies, common closure, heavy-dependency isolation, slow-test isolation, the orphan rule, and proc-macros.

Consumer: gerchowl/cx will adopt items 1-4 when it splits `crates/cx-kernel` into layered crates (W2.5).
---

# [Comment #1]() by [gerchowl]()

_Posted on November 8, 2026 at 02:36 PM_

Second consumer: **nerdmachines/quench** (ADR 0001 axes/framework layering), 2026-11-08. Requirements from an adversarial review of quench's hand-rolled version (quench PR #50):
- **Walk the resolved graph** (`cargo metadata` without `--no-deps`, `resolve.nodes`), not direct path deps only. A direct-only check passed `quench-core → quench-daemon{features=["image"]}`, i.e. a lower layer reaching an upper one through a crate that is in neither.
- **Same-group edges allowed** (e.g. `quench-surfaces-cli → quench-surfaces` inside one axis). quench's layers aren't a total order: framework < {clipboard, image, vector, surfaces}, and those axes must not depend on each other. So `layers.toml` needs a 'siblings may not depend on each other' rule, not only a linear order.
- **Per-layer external-crate denylist**: framework/portable crates must not reach Apple platform crates (`core-foundation*`, `security-framework*`, `objc2*`, `block2`, `cocoa` …). A Linux `cargo check` does NOT catch these: core-foundation-sys declarations compile on Linux because only linking is Apple-gated (probe: quench PR #50 round 4).
quench will carry a local script until this ships, then migrate.

