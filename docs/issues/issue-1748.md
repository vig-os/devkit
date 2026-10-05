---
type: issue
state: open
created: 2026-09-28T12:10:32Z
updated: 2026-09-29T15:53:56Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1748
comments: 2
labels: feature
assignees: none
milestone: none
projects: none
parent: 1771
children: none
synced: 2026-09-30T08:17:50.278Z
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

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:46 PM_

**Scope update from the publish-lane spike #1769** (verdict in the consolidation comment there; crates.io review on #1771).

This issue becomes the **crates.io channel implementation** of the new lane, with one design change: the publish mechanics are **managed, not seeded**. crates.io versions are permanent, and seeded copies never receive fixes.

- **Managed:** the `crates` job in the managed top-level `publish-release.yml` (#1778; must be top-level because crates.io Trusted Publishing reads `workflow_ref`, not `job_workflow_ref`). It covers:
  - `rust-lang/crates-io-auth-action`;
  - an index precheck that skips versions already published;
  - a `publish = false` audit;
  - `cargo publish --workspace --no-verify` (verification already ran in the dry-run gate);
  - 429 backoff that honours `Retry-After`;
  - a prerelease guard: **no release candidates to crates.io by default**, opt-in with dotted `rc.N`.
- **Seeded (as originally proposed here):** `cargo set-version --workspace` in `prepare-release-extension.yml`; the `cargo publish --workspace --dry-run` gate in `release-extension.yml`; `cargo-semver-checks` as an **advisory** gate.
- **Bytes:** `cargo publish` always repackages and cannot upload a prebuilt `.crate`, so byte identity with a Release asset is not achievable. Publish from `finalize_sha` (the tag), and treat the dry-run gate at the same SHA as the check that stands in for it.
- **Docs:** the first publish of each crate is manual (crates.io has no pending publishers). New crates are rate-limited to a burst of 5, then 1 per 10 minutes, so greenfield workspaces need a staged first publish.
- **release-plz:** documented as a supported opt-out, not a dependency.

Now blocked by #1778 (skeleton).


---

# [Comment #2]() by [gerchowl]()

_Posted on September 29, 2026 at 03:53 PM_

**Revised after the ADR review on PR #1785** (`docs/rfcs/ADR-publish-lanes.md`):
- **v1 is finals only**, enforced by the `resolve` job in #1778. Release candidates stay off by default even once #1787 lands.
- Register the trusted publisher against `publish-release.yml` + environment **`publish-crates`** (not `crates-io`).

