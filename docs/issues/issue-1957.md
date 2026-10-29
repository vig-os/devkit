---
type: issue
state: open
created: 2026-10-29T02:32:35Z
updated: 2026-10-29T02:32:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1957
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:28.729Z
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
