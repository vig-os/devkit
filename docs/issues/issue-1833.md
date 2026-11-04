---
type: issue
state: open
created: 2026-10-05T18:36:28Z
updated: 2026-10-05T21:36:42Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1833
comments: 3
labels: feature, priority:medium, area:workspace, effort:large
assignees: none
milestone: none
projects: none
parent: none
children: 1496, 1831, 1810, 1826, 1832
synced: 2026-10-06T08:50:56.655Z
---

# [Issue 1833]: [Tracking: cold adoption of devkit by a Rust project](https://github.com/vig-os/devkit/issues/1833)

Tracking issue for adopting devkit as a **Rust** consumer: one place to see what blocks a cold Rust adoption, ordered by what an adopter hits first.

## Context
The Rust pack shipped as a library (`nix/modules/rust.nix` plus `lib.mkRustProject`, #1429 / #1452), but the path into it did not. The most recent cold adoption (direnv mode, trunk workflow, solo profile) never found the pack. It hand-rolled `pkgs.cargo`/`rustc` in `extraPackages`, custom `cargo fmt`/`clippy` hooks, `justfile.project` recipes and a `buildRustPackage` derivation, which works but bypasses the pack's check suite. The items below are why.

## Entry point and discoverability
- [ ] #1496: L1/L4/L7 never shipped. There is no `nix flake init -t #rust`, no base `rustfmt`/`clippy`/`deny` statics, and no Rust `justfile.project` seeding, so a Rust repo's `just test` is a silent green no-op until the adopter rewrites it.
- [ ] #1831: MIGRATION.md says `rust` is an unshipped candidate module and recommends `extraPackages = [ pkgs.cargo pkgs.rustc ]`, which steers adopters away from `mkRustProject`.

## Correctness once adopted
- [ ] #1810: `mkRustProject` drops the `.vig-os` hook settings (`branchTypes`/`commitTypes`/`refsPolicy`/`refsOptionalTypes`), so a Rust scaffold fails deadnix/statix, and e.g. `DEVKIT_REFS_POLICY=optional` silently stops reaching the local commit-msg hook.
- [ ] Open question, to settle in #1496 or a new issue: `mkRustProject`'s nextest/doctest checks run inside the Nix build sandbox. Suites that need a PTY, process groups or signals (CLI wrappers, supervisors) can't run there, and on darwin the sandbox is stricter still. The pack should document, or provide, a per-test exclusion seam that keeps such tests in `just test`/CI rather than `nix flake check`.

## Hit by Rust adopters, but not Rust-specific
- [ ] #1826: the upgrade preflight treats untracked `target/` as dirty, blocking the upgrade that adds the Rust `.gitignore` fragment.
- [ ] #1832: the direnv flake template's `nixpkgs.follows = "vigos/nixpkgs"` makes every flake that consumes a Rust project's `packages` inherit devkit's whole input tree.

## Release (later)
- [ ] #1748: L6 release-seam templates (`cargo set-version`, publish dry-run, `cargo publish --workspace` with Trusted Publishing).
- [ ] #1783: binaries publish lane (managed cargo-dist asset builder into the train draft).

## Settled, for reference
- #1400 (pack design), #1427 (where checks live), #1450 (consumer hardening), #1488 (guardrails module), #1746 (release extension seam).
- #1025: CodeQL has no Rust leg, by decision.

## Done when
A cold `install.sh --mode direnv` on a repo with `Cargo.toml` yields:
- a flake on `mkRustProject` that passes its own hooks and honours `.vig-os`;
- `just lint`/`just test` that compile and test the crate;
- docs that point there.

All of it with no hand-written Rust plumbing.

---

# [Comment #1]() by [gerchowl]()

_Posted on October 5, 2026 at 06:46 PM_

Working through this list as one PR stack into `dev`, which then goes out as the next release candidate.

**Stack order** (each PR bases on the one before):
1. #1810: `mkRustProject` forwards the `.vig-os` hook settings. Lands first, because the template in step 3 depends on it.
2. #1834 (new, split out of the open sandbox question above): per-test exclusion seam for tests the Nix sandbox can't run.
3. #1496: L7 `#rust` template, L1 statics, L4 `justfile.project` seeding. Removes the consumer-matrix `EXPECTED_FAIL[rust]` marker.
4. #1831: docs point Rust adopters at the pack.
5. #1826: upgrade preflight no longer counts build output as a dirty tree.
6. #1832: direnv flake template input direction for projects that ship packages.

**Deferred:** #1748 and #1783 stay under "Release (later)". They are blocked on #1778 and #1786 (the publish-lane skeleton and the asset builder), and the cold-adoption "done when" bar doesn't need them.

---

# [Comment #2]() by [gerchowl]()

_Posted on October 5, 2026 at 07:24 PM_

The stack is open, bottom to top. Each PR bases on the one above it, and the bottom PR bases on `dev`:

| # | PR | Issue |
| --- | --- | --- |
| 1 | #1835 `fix(nix)`: forward the .vig-os hook knobs through mkRustProject | #1810 |
| 2 | #1836 `feat(nix)`: sandboxExcludes for mkRustProject's nextest check | #1834 |
| 3 | #1837 `feat`: seed the Rust pack on cold adoption (cargo recipes, tool configs, mkRustProject flake, `#rust` template) | #1496 (+ #1810's scaffold half) |
| 4 | #1838 `docs`: point Rust adopters at the Rust pack | #1831 |
| 5 | #1839 `fix`: upgrade preflight passes untracked output the upgrade will ignore | #1826 |
| 6 | #1840 `docs`: how a flake consumes a devkit project's packages | #1832 |

How the "done when" bar is met: the consumer matrix's new `rust-flake` cell runs exactly that path on every PR. It renders a cold `--mode direnv` scaffold of a Cargo repo, runs `nix flake check` on the seeded `mkRustProject` flake (fmt/clippy/nextest/doctest/doc/deny/package), runs the first-commit hooks, then `just sync/lint/test` inside the flake's shell, which must prove the crate's test ran. The `rust` cell's `EXPECTED_FAIL` marker is removed.

After final review, the stack merges into `dev` and goes out as the next release candidate.

---

# [Comment #3]() by [gerchowl]()

_Posted on October 5, 2026 at 09:36 PM_

The whole stack (#1835–#1840) is merged into `dev` after final review, all green.

`prepare-release` cut `release/1.19.0`. Release PR #1841 to `main` has c-vigo as reviewer. `1.19.0-rc1` gets published once #1841's CI is fully green.

The Rust-adoption items here close when 1.19.0 lands on `main`. #1748 and #1783 stay open ("Release (later)", blocked on #1778/#1786).

