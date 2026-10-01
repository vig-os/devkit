---
type: issue
state: closed
created: 2026-09-29T15:36:41Z
updated: 2026-09-30T17:51:24Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1774
comments: 2
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1783
synced: 2026-10-01T08:40:53.963Z
---

# [Issue 1774]: [[SPIKE] Publish lane: prebuilt binaries & installers (cargo-dist, Homebrew, signing)](https://github.com/vig-os/devkit/issues/1774)

Parent spike: #1769. Research the 2026 best practice for shipping prebuilt binaries and installers (Rust first, language-agnostic where possible) and decide what devkit manages.

## Motivation / why

The only supported path today is a hand-copied cargo-dist recipe (on `dev`, `docs/DOWNSTREAM_RELEASE.md` "cargo-dist adopter recipe"), because dist's generated CI undrafts the Release itself under `GITHUB_TOKEN` (bypasses promote, never fires `release: published`). The upstream fix — `undraft-release = false`, axodotdev/cargo-dist#2520 / #2521 — is **still open**.

## Proposed approach (strawman)

- Short term: turn the recipe into a managed-or-seeded tag-push workflow driven by `dist-workspace.toml` (dist as asset builder into the train's draft).
- Once #2521 lands: switch to dist's generated CI with `undraft-release = false`; devkit manages only the config contract and a drift check.
- Evaluate alternatives for non-Rust binaries (goreleaser for Go, generic matrix builds) and distribution extras: Homebrew tap, shell/PowerShell installers, `cargo binstall` metadata, macOS codesign/notarization, Windows signing.

## What already exists

cargo-dist recipe (on `dev`), draft-first + pre-publish assets window (#1746), `release-publish.yml` draft-before-tag ordering.

## Scope / questions

- [ ] cargo-dist maintenance status 2026 and the #2521 timeline — safe to bet on?
- [ ] Cross-compilation: native runners matrix vs. `cargo-zigbuild` vs. nix cross — what should the template default to?
- [ ] Per-binary attestations + checksums: dist-native or devkit's generic assets step (see GitHub Releases spike)?
- [ ] Homebrew tap publishing: needs a write token to another repo — fits the App token model (`docs/WORKFLOW_SECURITY.md`)?
- [ ] macOS notarization / Windows signing: in scope or explicitly out?

## Pitfalls

- dist's `plan` drift check fails on hand-edited generated CI.
- Tag-only candidates have no draft → asset workflow must no-op cleanly.
- Runner labels (`macos-14`, `ubuntu-24.04`) drift; `DEVKIT_CI_RUNNER` interplay.

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
**cargo-dist is a safe bet.** v0.33.0 shipped 2026-09-10, maintainers are actively merging, and on 2026-09-28 a maintainer said they were "fine with your proposed solution" on [#2520](https://github.com/axodotdev/cargo-dist/issues/2520). Treat [#2521](https://github.com/axodotdev/cargo-dist/pull/2521) as the thing that lets us delete the hand-copied recipe, not as a dependency the plan can't survive without.

**Alternatives:** GoReleaser v2.5+ (Rust via `cargo-zigbuild`), cargo-binstall, or a hand-rolled matrix.

## Choices
- **Cross-compilation default:** `cargo-zigbuild` on Linux for glibc, musl and windows-gnu; native `macos-14` / `windows-2022` runners for Darwin and MSVC; `cross` as an escape hatch.
- **Checksums and attestations:** **generic devkit step**, one attestor over every asset, rather than dist's per-asset attestations, so it works for non-Rust repos too.
- **Homebrew:** no OIDC is available, so mint an App installation token scoped to the tap repo (the `docs/WORKFLOW_SECURITY.md` shape). If the tap has branch protection, the App needs a bypass or a PR flow.
- **Signing:** macOS notarization is in scope (Sequoia's Gatekeeper). Bare Mach-O binaries can't be stapled, so first run needs an online check. Windows via Azure Trusted Signing is opt-in. Both are **seeded**, since the secrets are per repo.

## Split
- **Before #2521:** managed tag-push workflow (`dist build`, upload into the draft, sums and attestations, no-op without a draft). Seeded `dist-workspace.toml`, signing and tap config.
- **After #2521:** managed shrinks to a drift check plus `undraft-release = false`; dist's generated CI becomes the seeded part.

## New pitfalls
- Installer URLs bake in the tag and 404 until the Release is published.
- `macos-14` runners are Apple Silicon only.
- **Do not adopt `allow-dirty = ["ci"]`**: it disables drift protection globally.

Sources: [dist releases](https://github.com/axodotdev/cargo-dist/releases) · [dist #2396 Azure signing](https://github.com/axodotdev/cargo-dist/pull/2396) · [GoReleaser Rust](https://goreleaser.com/customization/builds/rust/) · [cargo-zigbuild](https://github.com/rust-cross/cargo-zigbuild) · [notarizing CLIs](https://www.randomerrata.com/articles/2024/notarize/)


---

# [Comment #2]() by [c-vigo]()

_Posted on September 30, 2026 at 05:51 PM_

Spike complete. The dated verdict is in the review above; the cross-cutting decision is recorded in `docs/rfcs/ADR-publish-lanes.md` (PR #1785, merged to `dev` as 36e74ccc), per #1769's rule that the channel spikes close when the ADR lands.

Implementation continues in: #1783 (binaries lane) (lane foundation: #1778).

