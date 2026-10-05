---
type: issue
state: open
created: 2026-09-29T15:45:30Z
updated: 2026-09-29T15:54:00Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1783
comments: 1
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1774
children: none
synced: 2026-09-30T08:17:36.729Z
---

# [Issue 1783]: [[FEATURE] Binaries publish lane: managed cargo-dist asset builder into the train draft](https://github.com/vig-os/devkit/issues/1783)

### Description

Implementation of the prebuilt-binaries channel for the publish-lane spike #1769 (review on #1774). Replace the hand-copied cargo-dist recipe with a managed tag-push workflow that builds into the train's draft Release.

### Problem Statement

dist's generated CI undrafts the Release itself under `GITHUB_TOKEN`. That bypasses promote, and because events from `GITHUB_TOKEN` start no workflows, `release: published` never fires. Today each Rust repo copies the recipe from `docs/DOWNSTREAM_RELEASE.md`. The upstream fix (axodotdev/cargo-dist#2520 / #2521, `undraft-release = false`) is open, and the maintainers have signalled acceptance.

### Proposed Solution

- **Now:**
  - **Managed:** a tag-push workflow that runs `dist build` locally, then globally, uploads into the draft with `--clobber`, attests its outputs (the seal gates on this), and does nothing when no draft exists (tag-only release candidates).
  - **Seeded:** `dist-workspace.toml` without `ci`, with the cross-compilation default `cargo-zigbuild` for Linux and windows-gnu and native macOS and MSVC runners.
  - **Seeded, opt-in:** macOS notarization and Windows Azure Trusted Signing (secrets are per repo); a Homebrew tap using an App installation token scoped to the tap repo.
- **After #2521 ships:** managed shrinks to a drift check plus `undraft-release = false`, and dist's generated CI becomes the seeded part.

### Alternatives Considered

GoReleaser (a viable alternative for non-Rust or mixed repos; document it, don't template it); `allow-dirty = ["ci"]` (rejected: disables drift protection globally).

### Additional Context

Pitfalls: `macos-14` runners are Apple Silicon only; installer URLs 404 until promote; bare Mach-O binaries can't be stapled.

### Impact

Rust CLI repos get binaries, installers and optionally Homebrew by declaring the channel.

### Changelog Category

Added

Refs: #1769, #1774

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:54 PM_

**Revised after the ADR review on PR #1785** (`docs/rfcs/ADR-publish-lanes.md`):
- **Build on the managed asset builder, #1786**, as a `binaries` channel with a matrix hook, rather than a parallel upload workflow. Now blocked by #1786.
- The seal (#1777) verifies each asset's attestation with this repo as signer, so dist outputs must be attested (by the asset builder, or by dist's `github-attestations`).

