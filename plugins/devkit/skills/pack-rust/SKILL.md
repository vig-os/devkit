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
**today**. The release-layer contracts a Rust repo needs shipped with #1746 — a pluggable pre-release format, the
draft-first Release-owner contract with its pre-publish assets window, and a standalone publish seam — so audit
those as configuration. The Rust pack's template layers are tracked in #1496 and have **not** shipped; report that
gap as a gap. Never describe an unmerged contract as if it were available, and never the reverse.

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

## 4. Release layer — check the three seams are wired

These shipped with #1746. Audit them as present-or-absent configuration, not as future work.

### Pre-release format

The train no longer hard-codes `-rcN`. Read the resolved format and report it:

```bash
sed -n 's/^DEVKIT_PRERELEASE_FORMAT=//p' .vig-os
```

Precedence is `release.yml`'s `pre-release-format` input, then this key, then the `rc{N}` default — which
reproduces today's `X.Y.Z-rcN` tags byte-identically, so an existing consumer needs no change. `{N}` is an
optional counter and `{YYYYMMDD}` a UTC date, so `alpha.{N}` gives `X.Y.Z-alpha.1` and `beta` gives `X.Y.Z-beta`.

Two things to flag when you find a non-default format:

- **Prefer a dotted counter** (`rc.{N}`, `alpha.{N}`). SemVer compares `rc10` *below* `rc9`, so an undotted
  counter sorts wrongly in any tooling that parses the version properly.
- **A format switch that would sort below an existing pre-release of the same `X.Y.Z` is refused** by the train.
  If a repo wants to move from `rc` to `alpha` mid-version, that is the refusal it will hit.

Also report any stray `X.Y.Z-*` tag: candidate discovery now lists every pre-release of the version, not only
`-rc*`, so a leftover tag such as `1.2.3-test` sorting above the next counter blocks candidates for that version.

### Release-object ownership — the draft window

The train **always** creates the GitHub Release as a draft, and `promote-release.yml` is the only step that flips
it to published. Between the draft's creation and promote there is a named pre-publish assets window in which a
consumer workflow may upload into it.

**Check that no other tool creates or publishes the Release for a train tag.** That is the whole contract, and it
is the one a Rust repo most often breaks.

```bash
ls dist-workspace.toml 2>/dev/null && grep -nE 'ci|create-release|github-release|hosting|installers' dist-workspace.toml
```

For cargo-dist specifically, read `docs/DOWNSTREAM_RELEASE.md` rather than assuming: **`create-release = false` is
not the fix.** cargo-dist uploads into the draft and then publishes it itself, which bypasses promote, makes the
Release immutable before late assets land, and fires no `release: published` event. No `github-release` or
`dispatch-releases` setting avoids it. The supported shape is cargo-dist as an **asset builder** with no `ci` key
at all, plus a consumer-owned tag-push workflow that uploads into the draft and never publishes it. Flag a
generated `.github/workflows/release.yml` from cargo-dist as a direct collision with the train's orchestrator
path.

### Live publish path

Irreversible outward pushes — crates.io, PyPI, a container registry — belong in the standalone seam, which fires
on `release: published`, i.e. after promote:

```bash
ls .github/workflows/publish-release-extension.yml 2>/dev/null
grep -nE 'environment:|id-token|permissions:' .github/workflows/publish-release-extension.yml 2>/dev/null
```

Report whether the seam is still the no-op seed or has been filled in. When it is filled in, check the three
invariants: the trigger is the point of no return (rolling back a GitHub Release does not retract a published
crate), an `environment:` with a required reviewer should gate the irreversible step, and each artefact should
have an idempotency precheck so a re-dispatch after a transient failure skips what already published.

`release-extension.yml` is **not** the place for this: it fires before the tag exists, so it structurally cannot
host a live publish. Flag any publish command found there.

### Still open

- **Pack template layers.** The toolchain, lint-table and project-recipe seeds that would make a Rust repo
  adoptable in one step are tracked in #1496 and have not shipped.

## 5. Hand back

A findings list, each entry with the evidence you read and the issue it belongs to. No file writes, no proposals
to hand-roll a seam that is already designed — an unmerged contract is a blocker to report, not a gap to fill
locally.
