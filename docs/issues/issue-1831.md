---
type: issue
state: open
created: 2026-10-05T18:36:03Z
updated: 2026-10-05T18:36:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1831
comments: 0
labels: docs, priority:medium, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: 1833
children: none
synced: 2026-10-06T08:50:57.459Z
---

# [Issue 1831]: [Docs: MIGRATION.md says the rust module is unshipped and steers Rust adopters away from mkRustProject](https://github.com/vig-os/devkit/issues/1831)

## Problem
The adopter-facing docs never lead a Rust consumer to the Rust pack (`nix/modules/rust.nix`, `lib.mkRustProject`, shipped since 1.9.0), and one passage contradicts it:

- `docs/MIGRATION.md` ("The native-build contract") still says: *"`native` is the only module shipped today; `geant4`, `rust`, `fortran`/`f2py`, and `root` are named candidates gated on a concrete consumer ask."*
- `docs/MIGRATION.md` ("Adding tools the image does not ship") recommends `extraPackages = [ pkgs.cargo pkgs.rustc … ]` as the preferred way to get Rust. That route bypasses the pack's check suite (fmt/clippy/nextest/doc/doctest/deny), the pinned toolchain and auditable builds.
- Neither `README.md` nor `docs/SOLO_ADOPTION.md` mentions the pack.

## Impact
A Rust adopter who follows the docs hand-rolls the toolchain, hooks and package derivation, and only finds the pack later by reading `nix/`. This happened on a real adoption.

## Proposed
- Fix both MIGRATION passages. Point Rust (and any shipped module) at `mkRustProject`, and keep the `extraPackages` example for genuinely ad-hoc tools.
- Have `init-workspace.sh` print a notice when `DEVKIT_LANGUAGES` gains `rust`, pointing at `lib.mkRustProject`, until the `#rust` template from #1496 makes that automatic.

Complements #1496 (template, statics and justfile seeding not shipped). It does not duplicate it: this issue is about the docs.

