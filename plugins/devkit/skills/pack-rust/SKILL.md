---
name: pack-rust
description: >-
  Audit a Rust repository against what the vigOS devkit Rust pack ships today: toolchain and flake layer, lint
  table ownership, and whether the project's own test and lint recipes actually compile anything rather than
  silently greening a build of nothing. Read-only. Names the release-layer contracts that are still open rather
  than pretending they exist. Use when asked about Rust support, the Rust pack, or Rust release wiring in devkit.
---

# devkit pack-rust

A read-only audit, and the proof that the extension seam takes more than one pack. It reports on what devkit ships
**today** and is explicit about what it does not: the Rust pack's template layers are tracked in #1496 and have
never been adopted cold, and the release-layer contracts a Rust repo needs are tracked in #1746 and are not
merged yet. Report the gap; never describe an unmerged contract as if it were available.

## 1. State lookup

Run `/devkit:status` first — the pack is a layer on top of an adopted scaffold, so the pin, the drift and the
workflow model all apply here too. If the repo is not scaffolded at all, hand off to `/devkit:adopt`.

## 2. Inspect what exists

```bash
ls Cargo.toml rust-toolchain.toml deny.toml clippy.toml rustfmt.toml dist-workspace.toml 2>/dev/null
grep -n '\[workspace' -A10 Cargo.toml 2>/dev/null
grep -nE '^\s*(test|lint)\b' justfile.project 2>/dev/null
grep -n 'rust' flake.nix 2>/dev/null | head -20
```

Report each layer as present / absent / hand-written:

- **Toolchain layer** — is the Rust toolchain resolved through the flake, or pinned twice (once in
  `rust-toolchain.toml`, once in the flake) and free to disagree?
- **Lint-table layer** — `deny.toml`, `clippy.toml`, `rustfmt.toml`: who owns each one, the repo or the shared
  guardrails? A hand-written copy of a guardrails file is drift that nothing reports.
- **Project recipe layer** — `justfile.project`'s `test` and `lint` recipes.
- **Workspace shape** — a virtual manifest with `[workspace.package] version` behaves very differently from a
  single crate when a release bumps versions.

## 3. The silent-green trap

This is the finding worth the most, so check it explicitly rather than assuming:

```bash
just test
just lint
```

A `test` recipe that resolves to nothing, or that runs against an empty target set, **passes**. A repo can green
its whole CI while compiling none of its own code. Report what the recipes actually invoked and how many targets
they touched, not just the exit status.

## 4. Release layer — what is still open

State these as open work, with their issue numbers, and stop. Do not write config for a contract that has not
merged, and do not name a workflow file that devkit does not ship yet.

- **Pre-release format.** The train's version model renders `X.Y.Z-rcN` and its tag discovery is built around that
  literal. A repo mid `0.1.0-alpha.1` cannot adopt without a version-series decision. A configurable format, and
  the manifest key that would set a per-repo default, are proposed in #1746.
- **Release-object ownership.** The train creates the GitHub Release as a draft; a build tool that also creates one
  collides with it by design. The draft-first "Release Owner" contract and its named pre-publish assets window are
  proposed in #1746. Until it merges, a cargo-dist repo must set `create-release = false` by hand and host into
  the draft.
- **Live publish path.** Nothing in the shipped train covers an irreversible outward push such as a crates.io or
  PyPI publish. The existing `release-extension.yml` seam fires **before** the tag exists, so it structurally
  cannot host one. A standalone seam triggered on a published Release is proposed in #1746.
- **Pack template layers.** The toolchain, lint-table and project-recipe seeds that would make a Rust repo
  adoptable in one step are tracked in #1496.

## 5. Hand back

A findings list, each entry with the evidence you read and the issue it belongs to. No file writes, no proposals
to hand-roll a seam that is already designed — an unmerged contract is a blocker to report, not a gap to fill
locally.
