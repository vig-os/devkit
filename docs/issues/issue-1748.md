---
type: issue
state: open
created: 2026-09-28T12:10:32Z
updated: 2026-09-28T12:10:32Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1748
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:54.424Z
---

# [Issue 1748]: [[FEATURE] Rust pack L6: seed templates for the three release seams (cargo set-version, publish dry-run, cargo publish --workspace + Trusted Publishing)](https://github.com/vig-os/devkit/issues/1748)

### Description

Rust language pack **L6** (release layer, per `docs/designs/0001-rust-language-pack.md`): seed templates for the three release seams #1746 establishes, so a Rust repo gets a working crates.io release path from the scaffold instead of hand-writing it.

Split out of #1746 as a follow-up (its "Follow-ups (out of scope for this cut)" section); belongs on the #1496 track.

### Problem Statement

#1746 ships the language-neutral **contract** (pluggable pre-release format, draft-Release-first owner, standalone `publish-release-extension.yml`). A Rust adopter still has to fill all three seams by hand — the same five workflows scitadel#208 hand-wrote and tessera would have to rediscover.

### Proposed Solution

Evidence-driven (#1519): offered only when `Cargo.toml` declares a workspace.

- `prepare-release-extension.yml` = `cargo set-version --workspace <version>`, guarded on `[workspace.package] version` being present, followed by `cargo update --workspace`, committed onto `release/X.Y.Z`.
- `release-extension.yml` = `cargo publish --workspace --dry-run --allow-dirty` at `finalize_sha` (publishability gate before the tag exists).
- `publish-release-extension.yml` = `cargo publish --workspace` (**atomic**, Cargo 1.90+, resolves not-yet-published inter-crate versions against locally packaged upstreams — not a hand-rolled per-crate loop, which burns crate versions on partial failure) with `rust-lang/crates-io-auth-action` Trusted Publishing, `environment: crates-io`, and an idempotency precheck that skips versions crates.io already has.
- PyPI Trusted Publishing as a **commented** `pypa/gh-action-pypi-publish` stub, not a baked `maturin-action` (wheel provenance is per-repo).
- **`publish = false` detection:** before `cargo publish --workspace`, list workspace members that would be published (`cargo metadata --no-deps`, `publish != []`) and fail loudly on members that are clearly not meant for crates.io (e.g. a pyo3 `cdylib` or wasm crate without `publish = false`). tessera's `tessera-py` / `tessera-wasm` are the motivating case.

### Alternatives Considered

- A Rust "release plugin" inside the train: rejected in #1746 (smallest denominator, #1519).

### Additional Context

- Parent: #1746. Track: #1496, #1400. Prior art: vig-os/scitadel#208.

### Impact

Additive; seeds are preserved consumer files, only offered to Rust workspaces.

### Changelog Category

Added

