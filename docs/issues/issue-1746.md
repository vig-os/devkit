---
type: issue
state: closed
created: 2026-09-28T11:52:38Z
updated: 2026-09-28T23:42:03Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1746
comments: 5
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:55.275Z
---

# [Issue 1746]: [Release train: first-class Rust release extension (crates.io, cargo-dist binaries, wheels) via a general publish/Release-owner seam](https://github.com/vig-os/devkit/issues/1746)

### Description

Make Rust (and Rust+Python) repos first-class citizens of the vigOS devkit release train, without turning the train into a Rust-aware release tool. The gap is three cleanly bounded general seams — a **pluggable pre-release format**, a formalised **draft-Release-first "Release Owner" contract** so a build tool (cargo-dist, ship, etc.) can populate an existing draft, and a **new standalone `publish-release-extension.yml` seam** for irreversible outward publishes on `release: published` (crates.io, PyPI, container registries, nix caches).

Language-neutral by construction. Every Rust-specific mechanism (cargo publish, cargo set-version, maturin, cargo-dist config) stays in consumer files. Motivating adopters: **vig-os/tessera** (Cargo workspace, cargo-dist, pyo3 abi3 wheel via nix — see [tessera#441](https://github.com/vig-os/tessera/issues/441) migration analysis and [tessera#440](https://github.com/vig-os/tessera/issues/440)) and **vig-os/scitadel** (already hand-wrote this shape in [scitadel#208](https://github.com/vig-os/scitadel/pull/208) — this issue is the "back-fill the shared seam so the third adopter doesn't rediscover it" cut).

### Problem Statement

Any Rust / Rust+Python repo adopting the train has to reinvent five workflows because two contracts refuse Rust conventions outright and a third is missing:

1. **Version model is `X.Y.Z + rcN` only.** `release-core.yml` (Compute publish version step, lines 224–282, [`assets/workspace/.github/workflows/release-core.yml#L224-L282`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L224-L282)) auto-increments an integer after the fixed `-rc` literal; the tag-discovery pattern hard-codes `${TAG_PREFIX}${VERSION}-rc*` at L251. There is no path for `-alpha.N`, `-beta.N`, `-pre.YYYYMMDD`, or bare `-alpha`. tessera is mid `v0.1.0-alpha.1` and cannot adopt without a version-series decision it should not have to make.

2. **Release-object ownership is train-fixed.** `release-publish.yml` (`Create GitHub Release` step) creates the tag ref *and* the draft Release. cargo-dist's default `announce`/`host` steps also `gh release create`. They collide by design. Every Rust adopter resolves the collision by hand — scitadel forked cargo-dist entirely and wrote a standalone `binaries.yml` that waits for the draft and uploads with `--clobber`. tessera today has cargo-dist creating the Release directly, which bypasses the draft the train wants to own (root cause of [tessera#440](https://github.com/vig-os/tessera/issues/440): cargo-dist announces the Release **published**, so `release-nix.yml` can never attach the wheel — HTTP 422 "Cannot upload assets to an immutable release").

3. **Live-publish path is unspecified.** Nothing in the shipped train covers `cargo publish` (with workspace-wide inter-crate ordering), Trusted Publishing (OIDC via `rust-lang/crates-io-auth-action`), PyPI wheel upload, or any other irreversible outward push. `release-extension.yml` fires **before** the tag exists (`release-core.yml`'s finalize precedes `release-publish.yml`), so it structurally cannot host a live publish. scitadel invented `publish-crates.yml` on `release: published`; every next Rust adopter will invent the same file. [#330](https://github.com/vig-os/devkit/issues/330) (closed) considered the asset-handoff half only — this issue is the missing altitude.

Related: [#1496](https://github.com/vig-os/devkit/issues/1496) (Rust pack L1/L4/L7 never shipped — L6 is the release layer this issue fills), [#1519](https://github.com/vig-os/devkit/issues/1519) (smallest-denominator — this cut ships **contract**, not language-specific opinions), [#1523](https://github.com/vig-os/devkit/issues/1523) (org stack matrix — the Rust seam recipe is exactly the "one definitive answer per capability × archetype" this argues for), [#1144](https://github.com/vig-os/devkit/issues/1144) (permission ceiling — why the new seam must be standalone, not a called workflow).

### Proposed Solution

Three general changes. Land as one PR.

#### 1. Pluggable pre-release format

Add a **format string**, not a bare label — the ecosystem uses dotted separators (`-alpha.1`, `-beta.1`, `-rc.1`) and sometimes bare labels (`-alpha`). A `${LABEL}${N}` template breaks tessera's own shipped `v0.1.0-alpha.1`.

- New `release.yml` / `release-core.yml` workflow_call input `pre_release_format` (default `"rc.{N}"`).
- `{N}` is optional (bare `-alpha` valid); `{YYYYMMDD}` supported for date-stamped pre-releases.
- Tag-discovery pattern is **derived** from the format, not hard-coded around `-rc*`.
- New `.vig-os` key `DEVKIT_PRERELEASE_FORMAT` for per-repo default.
- **Precedence (documented explicitly in `docs/DOWNSTREAM_RELEASE.md`, mirroring the CLI-override convention):** dispatch input > `.vig-os` > hardcoded `"rc.{N}"`.
- **Backwards-compat:** default `"rc.{N}"` reproduces today's `X.Y.Z-rcN` byte-identically — h5v and scitadel remain unchanged.
- **Monotonicity gate:** refuse a label switch that lowers the pre-release ordering for the same `X.Y.Z` (e.g. dispatching `1.2.3` with `alpha.{N}` when `1.2.3-rc21` already exists must fail — new counter would produce SemVer-lower `1.2.3-alpha.1`).

#### 2. "Release Owner" contract: draft-Release-first, formalised

Document explicitly what `release-publish.yml` already partly does, and generalise:

- The train **always** creates the GitHub Release as a **draft** (both `final` and `candidate`-with-`create-release: true`). `promote-release.yml` remains the only place a draft flips to published.
- **Named "pre-publish assets window"** between tag push and promote. Any consumer workflow may upload assets into the draft during that window (`gh release upload … --clobber`). The `release-extension.yml` seam covers assets within its ceiling; assets needing `contents: write` go in a consumer-owned `push: tags:` workflow (scitadel's `binaries.yml` pattern).
- **Sequencing rule:** `release-publish.yml` MUST create the draft **before** pushing (or simultaneously with) the tag ref — pass `--target <finalize_sha>` to `gh release create --draft` so the tag materialises together with the draft. Fixes the race where a tag-triggered build tool arrives before the Release exists (documented failure mode: [anderix/lux#91](https://github.com/anderix/lux/issues/91) — omitting `create-release = false` in cargo-dist loses the host job when something else beats it to the release).

Side-effect: this **structurally fixes** [tessera#440](https://github.com/vig-os/tessera/issues/440) for every adopter, because the draft window is the correct place to upload late assets.

**cargo-dist adopter recipe** (added to `docs/DOWNSTREAM_RELEASE.md`; verified against cargo-dist 0.32 source [`cargo-dist/src/backend/ci/github.rs`](https://github.com/axodotdev/cargo-dist/blob/main/cargo-dist/src/backend/ci/github.rs) and [config reference](https://axodotdev.github.io/cargo-dist/book/reference/config.html)):

```toml
# dist-workspace.toml
[dist]
create-release  = false   # devkit's release-publish.yml owns the draft
github-release  = "host"  # undraft happens LAST, after uploads succeed
# optional: dispatch-releases = true   # cleaner ordering (train dispatches cargo-dist)
```

`dist generate` produces this deterministically; the `plan` job's drift-check passes as long as consumers commit what it emits. **No hand-edit of `release.yml`** (which is important because cargo-dist's `plan` job fails on drift). Precedent for this "asset builder only" mode: axo's own `ship`, excelano fleet (xray/xled/paxc/etc.), documented in cargo-dist's own book.

#### 3. New standalone seam: `publish-release-extension.yml`

Ship a **third** consumer-owned seam alongside `release-extension.yml` and `prepare-release-extension.yml`. Standalone `workflow` (not `workflow_call`), template-seeded and preserved on upgrades, no-op default. Triggered by `release: published` (i.e. **after** promote flips the draft).

**Why standalone, not called:** crates.io and PyPI Trusted Publishing bind the OIDC subject to the **concrete workflow file path**. A `workflow_call` indirection changes the subject and forces every consumer to reconfigure TP against the reusable's path (this is the reason scitadel's `publish-crates.yml`/`binaries.yml` are standalone — the pattern is forced by the registry). Retry via `workflow_dispatch` on the tag is native for a standalone; on a called workflow it would have to be rebuilt.

**Permissions:** the seam owns its own token grant. Seeded default `permissions: contents: read, id-token: write` + narrow package scopes as needed. Deny-by-default preserved; no ceiling fiction since there's no orchestrator caller.

**Contract:** `release: published` payload + `workflow_dispatch` input `tag` for manual retry. Nothing else. The seam is intentionally free-form — irreversible publish paths (`cargo publish`, `twine upload`, `docker push`) look nothing alike per language.

**Documented invariants** (in `docs/DOWNSTREAM_RELEASE.md`):
- The `release: published` trigger is the point of no return. A rolled-back GitHub Release does **not** retract already-published crates.io/PyPI versions.
- Consumers SHOULD use `environment: <registry>` with a required reviewer to gate the irreversible step.
- Consumers SHOULD add per-artefact idempotency prechecks so a re-dispatch after transient failure skips already-published versions.

### Alternatives Considered

- **(A) Status quo — Rust consumers hand-write everything.** Rejected. Five repos rediscovering the same five workflows is the exact failure `#1519` documents. tessera#441 shows the migration cost is dominated by these three missing contracts, not by anything Rust-specific.
- **(B) Ship a Rust "release plugin" inside the train that owns `cargo publish` + binaries + wheels.** Rejected. Violates smallest-denominator (`#1519`); the train is language-neutral by design.
- **(C) Extend `release-extension.yml` per [#330](https://github.com/vig-os/devkit/issues/330) (closed) to pass asset files through to publish.** Rejected. Solves asset-handoff only. Does not address version format, Release-owner delegation, live-publish path, or Trusted Publishing OIDC. Wrong altitude — the actual delegation surface is the Release object itself, not one field on it.
- **(D) Fold changelog synthesis (git-cliff / release-plz per-crate) and a Rust language-pack L6 template set into this issue.** Rejected on reviewer advice: bundling either leaks Rust-specific opinions into a language-neutral train PR and muddles the review surface. Split as follow-ups (see below).

### Acceptance Criteria

- [ ] A repo can dispatch `release.yml` with `pre-release-format=alpha.{N}` and produce tag `v0.1.0-alpha.1`; default `rc.{N}` reproduces existing behaviour byte-identically.
- [ ] `DEVKIT_PRERELEASE_FORMAT` in `.vig-os` sets a per-repo default; dispatch input overrides it; docs record the precedence rule.
- [ ] Label-switch monotonicity gate refuses a switch that would lower pre-release ordering for the same `X.Y.Z`.
- [ ] `release-publish.yml` guarantees the draft Release exists before or simultaneous with the tag ref (via `gh release create --draft --target <sha>`), and the "pre-publish assets window" is named + documented in `docs/DOWNSTREAM_RELEASE.md`.
- [ ] `docs/DOWNSTREAM_RELEASE.md` carries the cargo-dist adopter recipe (`create-release = false` + `github-release = "host"`), and confirms `dist generate` output is committed without hand-edits.
- [ ] `assets/workspace/.github/workflows/publish-release-extension.yml` exists as a preserved seed (default no-op), triggered on `release: published` + `workflow_dispatch`, with seeded `environment:` and `permissions:` comments.
- [ ] A test that a scaffolded consumer's `publish-release-extension.yml` receives the correct payload from a promote-triggered `release: published`, and that a retry via `workflow_dispatch` reaches the same state.
- [ ] tessera can migrate off release-plz using only the three seams, cargo-dist configured as above, and a consumer-owned tag-push workflow for prebuilt binaries — no bespoke train workarounds required.
- [ ] scitadel's already-shipped `binaries.yml`/`publish-crates.yml` remains valid under the new contract (the new seam is opt-in; the standalone tag-push shape is unchanged).
- [ ] h5v's no-op seams remain valid; nothing in this cut requires a Rust consumer.
- [ ] [tessera#440](https://github.com/vig-os/tessera/issues/440) is structurally fixed once tessera migrates: the wheel uploads inside the draft window.

### Follow-ups (out of scope for this cut)

Filed separately after this lands, per reviewer scope guidance:

- **Changelog synthesis seam recipe** (`prepare-release-extension.yml` template using `git-cliff` — not `release-plz`, whose `--changelog-only` mode doesn't exist and which wants to own version/tag/PR itself). Optional for consumers who don't hand-author `## Unreleased`. Belongs alongside the Rust-pack track.
- **Rust language-pack L6 seed templates** on the `#1496` track: `prepare-release-extension.yml` = `cargo set-version --workspace` (with guards for `[workspace.package] version` presence and `cargo update --workspace` after) + `release-extension.yml` = `cargo publish --workspace --dry-run --allow-dirty` + `publish-release-extension.yml` = `cargo publish --workspace` (**atomic**, Cargo 1.90+, resolves not-yet-published inter-crate versions against locally packaged upstreams — **not** a hand-rolled per-crate loop, which burns crate versions on partial failure) with `rust-lang/crates-io-auth-action` Trusted Publishing. Also: PyPI TP as a commented `pypa/gh-action-pypi-publish` stub, not a baked `maturin-action` (wheel provenance is per-repo).
- **Note for the tessera adopter runbook (not this issue):** `tessera-py` (pyo3 cdylib) and `tessera-wasm` currently have no `publish = false`. `cargo publish --workspace` would try to push them. This must be set before the first cut on the train, or the publish seam will fail — flagged here so the tessera-side migration checklist captures it.

### Additional Context

**Current train contract — file/line references:**

- Orchestrator: [`assets/workspace/.github/workflows/release.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release.yml) — dispatches `release-core.yml` + `release-extension.yml` (with the `contents:read, packages:write, id-token:write, attestations:write` ceiling per `#1144`) + `release-publish.yml`.
- Version model: [`release-core.yml#L14`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L14), [`#L24`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L24), [`#L224-L282`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L224-L282) (Compute publish version — `-rc` literal, integer counter, tag discovery under `${TAG_PREFIX}${VERSION}-rc*`).
- Release owner today: [`release-publish.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-publish.yml) — Create release tag + Create GitHub Release (currently creates tag ref first, then draft; sequencing rule tightens this).
- Read-only seam (asset window for the ceiling scope): [`release-extension.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-extension.yml).
- Mutating seam: [`prepare-release-extension.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/prepare-release-extension.yml).
- Extension hook docs: [`docs/DOWNSTREAM_RELEASE.md`](https://github.com/vig-os/devkit/blob/main/docs/DOWNSTREAM_RELEASE.md) ("Extension Hook", "Prepare-Release Extension Hook", "Permission ceiling").

**Motivating adopters (already-written prior art):**

- [vig-os/scitadel#208](https://github.com/vig-os/scitadel/pull/208) (merged) — full Rust migration hand-writing all three seams: `prepare-release-extension.yml` = `cargo set-version --workspace`; `release-extension.yml` = crates.io publishability gate at `finalize_sha`; standalone `publish-crates.yml` on `release: published` with `environment: crates-io`; standalone `binaries.yml` on `push: tags:` uploading into the draft. This issue's seam matches that shape.
- [vig-os/tessera#441](https://github.com/vig-os/tessera/issues/441) (open, DECISION) — migration-cost analysis. All four blockers listed there collapse to the three sections above once this issue's cut lands.
- [vig-os/tessera#440](https://github.com/vig-os/tessera/issues/440) (open, bug) — 422 on post-publish wheel upload; structurally fixed by section 2.

**Cross-refs:**

- Devkit prior art: [#1400](https://github.com/vig-os/devkit/issues/1400) (Rust language pack, closed), [#1496](https://github.com/vig-os/devkit/issues/1496) (L1/L4/L7 never shipped — this is the L6 side), [#1519](https://github.com/vig-os/devkit/issues/1519) (smallest denominator), [#1523](https://github.com/vig-os/devkit/issues/1523) (org stack matrix), [#330](https://github.com/vig-os/devkit/issues/330) (closed — asset handoff only, wrong altitude), [#1144](https://github.com/vig-os/devkit/issues/1144) (permission ceiling — why the third seam is standalone), [#1710](https://github.com/vig-os/devkit/issues/1710) (COMMIT_APP env-secret handling; new seam inherits the same pattern).

**External:**

- cargo-dist config reference (verified): `create-release`, `github-release`, `dispatch-releases`, host job — [axodotdev.github.io/cargo-dist/book/reference/config.html](https://axodotdev.github.io/cargo-dist/book/reference/config.html).
- cargo-dist source (host job generation with `create-release = false`): [`cargo-dist/src/backend/ci/github.rs`](https://github.com/axodotdev/cargo-dist/blob/main/cargo-dist/src/backend/ci/github.rs).
- crates.io Trusted Publishing: [rust-lang/crates-io-auth-action](https://github.com/rust-lang/crates-io-auth-action) (~30 min OIDC-subject-scoped token; per-crate registration; workspace-atomic publish is `cargo publish --workspace` from Cargo 1.90).
- PyPI Trusted Publishing: [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish).

### Impact

- **Beneficiaries:** all future Rust or Rust+Python devkit adopters. Immediate first three: tessera (blocked today), scitadel (converges its already-hand-written shape onto the shared seed), any subsequent Rust repo (cold-start cost drops from a week to a scaffold).
- **Compatibility:** additive. Every existing adopter (h5v, scitadel, the devkit repo itself) sees byte-identical behaviour because the default `pre_release_format` is `"rc.{N}"`, the new seam defaults to no-op, and the draft-first sequencing is what `release-publish.yml` already does (only the ordering guarantee tightens).
- **Not breaking**, but every consumer's `docs/DOWNSTREAM_RELEASE.md` reader will see the third seam appear — worth a one-line note in the next release notes.

### Changelog Category

Added

https://claude.ai/code/session_01XdERKMVDAwfMJSKdTytNnK

---

# [Comment #1]() by [gerchowl]()

_Posted on September 28, 2026 at 11:53 AM_

Related: #1744 (devkit Claude plugin — state-lookup-first `/devkit-release-*` skills should wrap the seams defined here).

https://claude.ai/code/session_01XdERKMVDAwfMJSKdTytNnK

---

# [Comment #2]() by [gerchowl]()

_Posted on September 28, 2026 at 12:10 PM_

## Correction: the cargo-dist recipe in this issue does not work as written

The recipe proposes `create-release = false` + `github-release = "host"` so that cargo-dist uploads into the train's draft. With `create-release = false`, cargo-dist **publishes the draft itself** at the end of its host (or announce) job:

- Config reference, v0.32.0: [`cargo-dist/src/config/v1/hosts/github.rs#L18-L20`](https://github.com/axodotdev/cargo-dist/blob/6886366640dd4da83d33ba55cc04aa58423cbad2/cargo-dist/src/config/v1/hosts/github.rs#L18-L20): *"If false, dist will assume a draft Github Release already exists with the title/body you want. At the end of a successful publish it will **undraft** the Github Release."*
- Generator, v0.32.0: [`cargo-dist/src/backend/ci/github.rs#L512-L514`](https://github.com/axodotdev/cargo-dist/blob/6886366640dd4da83d33ba55cc04aa58423cbad2/cargo-dist/src/backend/ci/github.rs#L512-L514) emits `gh release edit <tag> --draft=false`, run right after `gh release upload <tag> artifacts/*` ([`publish_github.yml.j2#L43`](https://github.com/axodotdev/cargo-dist/blob/6886366640dd4da83d33ba55cc04aa58423cbad2/cargo-dist/templates/ci/github/partials/publish_github.yml.j2#L43)). Unchanged at HEAD (0.33.0).

`github-release` only chooses *which* job runs the undraft, and `dispatch-releases` only changes the trigger. No config option suppresses the undraft. Consequences:

1. The Release is published **before** promote-release.yml, and promote's draft validation then fails.
2. Once published, the Release is immutable, so late assets such as tessera's wheel still get the 422 from vig-os/tessera#440.
3. The publish uses `GITHUB_TOKEN`, so `release: published` never fires, and the new `publish-release-extension.yml` seam would never run (same trap as vig-os/tessera#438).

**What ships instead:** cargo-dist as an **asset builder only**. Keep `hosting = ["github"]` so the curl|sh installers still point at the GitHub Release download URLs. Drop cargo-dist's generated CI: omit `ci`, which cargo-dist tolerates when `hosting` is explicit, see [`host.rs` `select_hosting`](https://github.com/axodotdev/cargo-dist/blob/6886366640dd4da83d33ba55cc04aa58423cbad2/cargo-dist/src/host.rs). A consumer-owned `push: tags:` workflow then runs `dist build` and `gh release upload --clobber` into the train's draft. Because `release-publish.yml` now creates the draft **before** the tag ref, that workflow always finds the draft. This needs no hand-edit of generated files, has no `plan` drift check to fight, and keeps the installers. The recipe is in `docs/DOWNSTREAM_RELEASE.md` → "cargo-dist adopter recipe" in the PR for this issue.

Also corrected while implementing:

- **Default format is `rc{N}`, not `rc.{N}`.** `rc.{N}` would publish `X.Y.Z-rc.1`, which contradicts the byte-identical `X.Y.Z-rcN` acceptance criterion. `rc.{N}` is documented as the SemVer-friendly choice for new repos, because SemVer ranks `rc10` below `rc9`.
- **The monotonicity gate only blocks pre-release label switches.** An existing *final* `X.Y.Z` tag produces a warning, not a refusal. After a failed final run the tag stays under the forward-fix policy, and a new candidate of the same version is the documented recovery.
- **A draft Release cannot "materialise the tag together with the draft".** GitHub creates a draft's tag only on publish. So the draft is created with `--target <finalize_sha>` first and the tag ref is POSTed afterwards. A failed tag POST discards the orphan draft.

## Follow-ups filed

- #1747: changelog synthesis recipe (`git-cliff`) for `prepare-release-extension.yml`
- #1748: Rust pack L6 seed templates for the three seams, including `publish = false` detection (the tessera-py / tessera-wasm case)
- #1749: promote-release candidate-tag cleanup generalised to the configured pre-release format (today it prunes only `-rc*`)


---

# [Comment #3]() by [gerchowl]()

_Posted on September 28, 2026 at 09:17 PM_

Cross-ref: filed #1754 — **data release lane** (CalVer data artefacts on their own tag namespace, integrity contract, mirror-target seam).

It is a sibling cut, not an overlap: #1746 generalises the train for a second *language*, #1754 for a second *artefact class*. The one shared surface is **§2 of this issue** — draft-Release-first plus the named pre-publish assets window. #1754 depends on it and is the case that makes it load-bearing rather than tidy: ~1 GB assets that need upload retries, and which under devkit's own immutable-releases policy can only be attached while the Release is still a draft.

No dependency on §1 (pre-release format) or §3 (`publish-release-extension.yml`) — a data refresh is not a code release and must not require one, so it cannot ride a `release: published` seam.

---

# [Comment #4]() by [gerchowl]()

_Posted on September 28, 2026 at 11:31 PM_

Implemented by #1750 (merged). Follow-ups: #1747, #1748, #1749.

---

# [Comment #5]() by [gerchowl]()

_Posted on September 28, 2026 at 11:42 PM_

Upstream follow-up for the cargo-dist undraft behaviour: issue axodotdev/cargo-dist#2520 and implementation PR axodotdev/cargo-dist#2521 (`undraft-release = false` keeps the upload into the train's draft but skips `--draft=false`). Once released, the cargo-dist adopter recipe in `docs/DOWNSTREAM_RELEASE.md` can switch to dist's generated CI instead of the hand-written tag-push workflow.

