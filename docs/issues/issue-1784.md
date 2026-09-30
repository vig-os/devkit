---
type: issue
state: open
created: 2026-09-29T15:45:33Z
updated: 2026-09-29T15:45:33Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1784
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1776
children: none
synced: 2026-09-30T08:17:36.089Z
---

# [Issue 1784]: [[FEATURE] Nix: seeded CI cache + opt-in trusted release-cache push](https://github.com/vig-os/devkit/issues/1784)

### Description

Implementation of the Nix lane for the publish-lane spike #1769 (review on #1776). Per that review it is **CI infrastructure, not a `DEVKIT_PUBLISH` channel**: a seeded CI cache plus an opt-in trusted release-cache push.

### Problem Statement

Consumer flakes that export packages have no binary cache, so users rebuild from source and CI caching is ad hoc. devkit's own two-tier setup (the trusted blocking Cachix push in `release.yml`, plus `nix-cachix.yml`) is not available to consumers.

### Proposed Solution

- **Seeded CI cache:** `nix-community/cache-nix-action` with GC settings (per repo, untrusted).
- **Managed release-cache push** (opt-in `.vig-os` flag): an idempotent `cachix push` of the release closure in the **pre-publish window**, written only by the tag-protected trusted job, with per-repo write tokens.
- **Seeded:** a `nixConfig.extra-substituters` / `extra-trusted-public-keys` block in the flake template; document `accept-flake-config`.
- **Not adopted:** FlakeHub flake publishing (lock-in; `github:` refs against train tags suffice), and Magic Nix Cache (deprecated 2025-02-01).

### Alternatives Considered

FlakeHub Cache (OIDC, but paid per member and no ad-hoc push); attic (self-hosted, still labelled a prototype).

### Additional Context

Cachix has no OIDC as of Sep 2026, so a token is unavoidable. Same-repo PRs can poison a shared writable cache, so separate the CI and release caches. The 5 GiB OSS tier needs pinning and GC.

### Impact

Nix consumers get substitutable releases and faster CI.

### Changelog Category

Added

Refs: #1769, #1776

