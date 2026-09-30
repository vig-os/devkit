---
type: issue
state: open
created: 2026-09-29T15:36:46Z
updated: 2026-09-29T15:41:46Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1776
comments: 1
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1784
synced: 2026-09-30T08:17:41.107Z
---

# [Issue 1776]: [[SPIKE] Publish lane: Nix binary caches & flake distribution (Cachix, FlakeHub, attic)](https://github.com/vig-os/devkit/issues/1776)

Parent spike: #1769. Research the 2026 best practice for publishing Nix outputs (binary caches, flake distribution) and decide what devkit manages for consumers.

## Motivation / why

devkit pushes its own closures to Cachix (`nix-cachix.yml`, blocking push on the trusted release path in `release.yml`), but consumers whose flakes export packages have no lane: users rebuild from source, and CI caches are ad hoc.

## Proposed approach (strawman)

- Managed opt-in: push release closures to a declared cache after build; cache choice evaluated (Cachix, FlakeHub Cache, self-hosted attic, Magic Nix Cache for CI-only).
- Evaluate FlakeHub flake publishing (`flakehub-push`, semver flake refs) as the "registry" analogue for flakes.

## What already exists

`nix-cachix.yml`, `release.yml` Cachix push, `nix-image.yml`, flake modules (`tests/test_flake_modules.py`), `docs/NIX.md`, `update-nixpkgs*.yml`.

## Scope / questions

- [ ] Cache options 2026: Cachix vs FlakeHub vs attic vs GitHub-hosted — auth model (OIDC?), cost, signing keys.
- [ ] Is flake publishing (FlakeHub) best practice or vendor lock-in? Alternatives (plain git tags + `github:` refs)?
- [ ] Should consumers push to the org cache (shared key/trust) or per-repo caches?
- [ ] Separation of CI cache (ephemeral) vs. release cache (trusted, signed) — upstream already distinguishes the "trusted publish path".

## Pitfalls

- Cache signing keys are long-lived secrets — conflicts with the OIDC-everywhere goal unless the provider supports OIDC.
- Pushing untrusted PR builds into a release cache poisons it.
- Closure size / cost for large projects.

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
**Reclassify: this is CI infrastructure, not a release-train publish channel.** The cache only saves bandwidth and never affects release correctness; a `github:` flake ref works with an empty cache. Recommendations:
- Keep **Cachix** for the trusted release cache.
- Add **`nix-community/cache-nix-action`** for per-repo CI caching.
- **Skip FlakeHub flake publishing.** It is lock-in (`flakehub.com/f/...` URLs spread through consumers' repos), and `github:owner/repo/<tag>` refs against train tags already work.

## Options
- **Cachix:** long-lived token only, **no OIDC** as of Sep 2026. Standard substituter, so leaving costs little.
- **FlakeHub Cache:** OIDC, paid per member, no ad-hoc push, no self-hosting.
- **attic:** self-hosted and active, but its docs still call it a prototype.
- **Magic Nix Cache:** **deprecated 2025-02-01**; do not adopt.

## Trust model
Use **two caches**:
- `<org>-ci`: untrusted; PRs push here; short retention.
- `<org>-release`: written only by the tag-protected trusted job, the same shape as devkit's blocking push in `release.yml`.

Consumers read from the release cache through `nixConfig.extra-substituters` / `extra-trusted-public-keys`. Use per-repo write tokens and no shared write key.

## Split
- **Managed:** a release cache-push workflow (idempotent `cachix push` of the closure, run in the pre-publish window) and the CI-cache seed.
- **Seeded:** the `nixConfig` substituter and key block in the flake template.
- **Repo:** the flake outputs and the cache/token registration.

## New pitfalls
- `nixConfig` substituters need `accept-flake-config` or the user's trust; otherwise Nix silently rebuilds from source.
- **Same-repo PRs** can poison the cache too, not only forks.
- Cachix's 5 GiB OSS tier needs pinning and GC.

Sources: [Cachix security](https://docs.cachix.org/security) · [cachix-action](https://github.com/cachix/cachix-action) · [FlakeHub Cache](https://docs.determinate.systems/flakehub/cache/) · [attic](https://docs.attic.rs/) · [Magic Nix Cache deprecation](https://github.com/DeterminateSystems/magic-nix-cache-action) · [cache-nix-action](https://github.com/nix-community/cache-nix-action) · [Tweag untrusted CI](https://www.tweag.io/blog/2019-11-21-untrusted-ci/)


