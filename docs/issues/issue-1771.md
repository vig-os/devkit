---
type: issue
state: closed
created: 2026-09-29T15:36:32Z
updated: 2026-09-30T17:51:17Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1771
comments: 2
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1748
synced: 2026-10-01T08:40:55.579Z
---

# [Issue 1771]: [[SPIKE] Publish lane: crates.io (Trusted Publishing, atomic workspace publish, semver gates)](https://github.com/vig-os/devkit/issues/1771)

Parent spike: #1769. Research the 2026 best practice for publishing Rust crates to crates.io and decide what devkit manages. Overlaps with #1748 (Rust L6 seam templates) — this spike validates #1748's design before it is implemented, and asks whether it should be **managed** rather than seeded.

## Motivation / why

#1748 proposes seeded templates; seeded means each repo owns its copy forever and fixes don't propagate. crates.io versions are permanent (yank ≠ delete), so the lane must be right the first time.

## Proposed approach (strawman)

- `rust-lang/crates-io-auth-action` Trusted Publishing, `cargo publish --workspace` (atomic, Cargo 1.90+), idempotency precheck against the index, `publish = false` detection.
- `cargo publish --workspace --dry-run` as a pre-tag gate in the release-extension seam; `cargo set-version` at prepare time.
- Evaluate whether `release-plz` / `cargo-release` / `cargo-smart-release` are the 2026 norm and whether devkit should interoperate or stay tool-agnostic.

## What already exists

`publish-release-extension.yml` stub (on `dev`), #1748 design, scitadel#208 (hand-written reference), cargo-dist recipe in `docs/DOWNSTREAM_RELEASE.md`.

## Scope / questions

- [ ] Trusted Publishing status 2026: does crates.io accept reusable-workflow / `job_workflow_ref` claims? Required `environment`?
- [ ] Is `cargo publish --workspace` robust enough (partial failure, rate limits on new crates)?
- [ ] `cargo-semver-checks` as a release gate — table stakes or optional?
- [ ] Prereleases: publish `X.Y.Z-rc.N` to crates.io or not?
- [ ] Does crates.io support provenance / attestations in 2026 (RFC status)?

## Pitfalls

- New-crate rate limits and the "first publish must be manual before Trusted Publishing can be configured" chicken-and-egg (verify if still true).
- Burned versions on partial workspace publish.
- OIDC subject bound to the workflow filename — the managed filename is a forever-contract.

## Acceptance criteria

- [ ] Dated verdict (verified-on / verified-how) on the 2026 best practice for this channel, with primary sources (registry docs, official actions)
- [ ] Gap table: best practice vs. what devkit ships today
- [ ] Concrete split: **devkit owns** (managed) / **devkit seeds** (template) / **repo owns** (build recipe, registry registration)
- [ ] Prerelease policy for this channel decided
- [ ] Implementation issue(s) filed, or an explicit "won't do" with reason

## References

Parent: #1769 · #1746 · #1748 · #1523 · #1519 · `docs/DOWNSTREAM_RELEASE.md` (on `dev`)

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:41 PM_

> Round-1 specialist review (fresh context, research only). Verified 2026-09-29 against primary sources; claims the reviewer could not verify are marked UNVERIFIED. Consolidated verdict: #1769.

## Verdict
**Make #1748's publish mechanics MANAGED, not seeded.** Use `rust-lang/crates-io-auth-action` and `cargo publish --workspace`, with an index precheck that skips versions already published, a `publish = false` audit and a dry-run gate. Stay tool-agnostic: document release-plz as a supported opt-out, because it owns the whole prepare→tag→publish loop and collides with the train.

## Facts
- Trusted Publishing binds owner/repo + **top-level workflow filename** + an optional environment. **Reusable workflows are not supported.** The **first publish of each crate is manual**, and there is no pending-publisher concept (unlike PyPI).
- `cargo publish --workspace` has been stable since Cargo 1.90. Verification is atomic, **uploads are not transactional**, and a partial failure burns versions.
- Rate limits: **new crates burst 5, then 1 per 10 min**. A greenfield workspace with more than 5 crates cannot publish in one shot.
- **No provenance or attestations on crates.io** (RFC 3403 still a proposal).

## Prereleases
**Don't publish `-rc.N` to crates.io by default.** They are permanent, and `^` requirements never resolve to them. Offer an opt-in that requires dotted `rc.N`.

## Split
- **Managed:** OIDC auth, index precheck, `publish=false` audit, `cargo publish --workspace --no-verify` (verification already ran in the dry-run, and retries outlive the 30-min token otherwise), 429 backoff honouring `Retry-After`, and a prerelease guard.
- **Seeded:** the dry-run gate in `release-extension.yml`, `cargo set-version --workspace` in `prepare-release-extension.yml`, and `cargo-semver-checks` as an **advisory** gate (blocking produces false positives on workspace-versioned crates).
- **Repo:** manual first publish, Trusted Publishing config, `publish = false` markers, `[workspace.package] version`, docs.rs metadata.

Sources: [crates.io TP](https://crates.io/docs/trusted-publishing) · [RFC 3691](https://rust-lang.github.io/rfcs/3691-trusted-publishing-cratesio.html) · [Cargo changelog](https://doc.rust-lang.org/beta/cargo/CHANGELOG.html) · [rate limits](https://crates.io/docs/rate-limits) · [tweag on workspace publish](https://www.tweag.io/blog/2025-07-10-cargo-package-workspace/)


---

# [Comment #2]() by [c-vigo]()

_Posted on September 30, 2026 at 05:51 PM_

Spike complete. The dated verdict is in the review above; the cross-cutting decision is recorded in `docs/rfcs/ADR-publish-lanes.md` (PR #1785, merged to `dev` as 36e74ccc), per #1769's rule that the channel spikes close when the ADR lands.

Implementation continues in: #1748 (crates.io lane) (lane foundation: #1778).

