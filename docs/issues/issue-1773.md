---
type: issue
state: open
created: 2026-09-29T15:36:38Z
updated: 2026-09-29T15:41:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1773
comments: 1
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1781, 1782
synced: 2026-09-30T08:17:42.690Z
---

# [Issue 1773]: [[SPIKE] Publish lane: npm (Trusted Publishing, provenance, dist-tags)](https://github.com/vig-os/devkit/issues/1773)

Parent spike: #1769. Research the 2026 best practice for publishing npm packages and decide what devkit manages. **devkit has nothing for npm today** — no template, stub or recipe (#988 only called it "a small per-repo hook").

## Motivation / why

vig-os has JS/TS consumers (e.g. commit-action, frontends per #1523). The npm ecosystem went through major supply-chain incidents in 2025 (self-propagating token-stealing worms), after which npm shipped Trusted Publishing (OIDC) and tightened token policy. A hand-rolled `npm publish` with an `NPM_TOKEN` secret is now the anti-pattern.

## Proposed approach (strawman)

- npm Trusted Publishing (OIDC, requires a recent npm CLI) with automatic provenance; no `NPM_TOKEN`.
- RCs → `next` dist-tag, finals → `latest`; never let a prerelease take `latest`.
- Package-manager agnostic build (`just dist-npm`), publish with the npm CLI (or pnpm/yarn equivalents if they support OIDC).
- Monorepos/workspaces: decide scope (changesets-style multi-package is likely out of scope for the train).

## What already exists

Nothing npm-specific. `node` capability module contributes `nodejs` to the shell. Publish seam on `dev`.

## Scope / questions

- [ ] Trusted Publishing status 2026: minimum npm CLI, reusable-workflow support, required `environment`, scoped vs unscoped packages.
- [ ] Current token policy (granular token lifetimes, classic token removal, 2FA) — what breaks for repos still on tokens?
- [ ] Provenance: automatic with OIDC? verification story (`npm audit signatures`)?
- [ ] GitHub Actions *published as actions* (commit-action): is the marketplace/`dist/` model a separate channel? (see `docs/DOWNSTREAM_RELEASE.md` dist example)
- [ ] JSR as a secondary target — relevant or noise?

## Pitfalls

- `npm publish` of a prerelease without `--tag` moves `latest`.
- `npm unpublish` 72-hour window; versions can never be reused.
- `private: true` packages and workspace roots must be excluded by evidence, not guesswork.

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
The token era is over. **Classic tokens were permanently revoked on 2025-12-09.** Granular write tokens last at most 90 days and require 2FA, and "bypass-2FA" tokens lose publish rights around Jan 2027. devkit must never seed an `NPM_TOKEN`.

## Facts
- Trusted Publishing needs **npm CLI >= 11.5.1** (use >= 11.5.2) and **Node >= 22.14**.
- Provenance is **automatic** under Trusted Publishing. `environment:` is optional.
- It binds to the **caller workflow filename**; reusable workflows fail with silent 404s.
- **The first publish cannot use OIDC:** the package must already exist, so bootstrap it manually.
- Since 2026-09-03, a Trusted Publishing config must allow at least one action, and staged releases wait for a malware scan, so publish jobs can run longer.
- pnpm >= 12 and yarn >= 4.18.1 support OIDC natively. Bun is UNVERIFIED, so build with Bun and publish with npm.

## Policy
- Release candidates go to `--tag next` (derived automatically from the SemVer suffix); finals go to `latest`.
- **GitHub Actions on the Marketplace are a separate channel:** committed `dist/` plus moving major tags. Seed that lane separately.
- **JSR:** an optional seed for TypeScript libraries, not a default.

## Split
- **Managed:** the publish job (OIDC, `npm view` idempotency precheck, next/latest routing, `npm audit signatures`).
- **Seeded:** the `just dist-npm` recipe and `.npmrc`.
- **Repo:** first manual publish, npmjs.com Trusted Publishing registration, `private` flags. **Workspaces need one registration per child package.**

Sources: [npm trusted publishers](https://docs.npmjs.com/trusted-publishers/) · [TP GA](https://github.blog/changelog/2025-07-31-npm-trusted-publishing-with-oidc-is-generally-available/) · [classic tokens revoked](https://github.blog/changelog/2025-12-09-npm-classic-tokens-revoked-session-based-auth-and-cli-token-management-now-available/) · [bypass-2FA restriction](https://github.blog/changelog/2026-07-31-restricting-npm-bypass-2fa-granular-access-tokens/) · [npm/cli#8544](https://github.com/npm/cli/issues/8544) · [publishing actions](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/release-and-maintain-actions)


