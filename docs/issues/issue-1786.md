---
type: issue
state: open
created: 2026-09-29T15:53:01Z
updated: 2026-09-29T15:53:01Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1786
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1770
children: none
synced: 2026-09-30T08:17:35.633Z
---

# [Issue 1786]: [[FEATURE] Release asset builder: managed tag-push build + upload + attest into the train draft](https://github.com/vig-os/devkit/issues/1786)

### Description

A managed **release asset builder**: a tag-push workflow that runs the repo's `just dist-<channel>` for each declared channel that produces files, uploads the outputs into the train's draft GitHub Release, and attests them. Recorded in `docs/rfcs/ADR-publish-lanes.md` §4 (spike #1769). Added after the ADR review found that nothing owned the bytes PyPI is meant to publish (#1779).

### Problem Statement

The ADR requires PyPI to publish **the exact bytes on the Release**, so the Release attestation and the PEP 740 attestation describe the same files, and requires the seal (#1777) to verify an attestation on every asset. No workflow builds, uploads or attests those assets. The only existing path is the cargo-dist recipe, which each repo copies by hand.

### Proposed Solution

- Managed `assets/workspace/.github/workflows/release-assets.yml`, triggered on `push: tags` matching `DEVKIT_TAG_PREFIX`.
- It resolves the draft with `gh release view --json isDraft`. If there is **no Release** (a tag-only candidate), it exits 0. If the Release is already **published**, it errors.
- For each declared channel with a `dist-<channel>` recipe (`pypi` first; `binaries` via #1783), it runs the recipe, runs `actions/attest-build-provenance` over the outputs, and uploads with `gh release upload --clobber`. Re-runs are idempotent.
- It uploads with the Release App token, consistent with promote. Permissions: `contents: read`, `id-token: write`, `attestations: write`, `artifact-metadata: write`.
- Where attestations are unavailable (a private repo without GitHub Enterprise Cloud), it skips attesting with a warning, matching the seal's `auto` fallback.
- The job summary lists each asset with its digest, so the seal and registry jobs can cross-check.

### Alternatives Considered

- Build inside the registry job at publish time: rejected; the bytes would differ from the Release assets.
- Build in `release-extension.yml`: rejected; it runs before the draft and the tag exist, so it cannot upload.

### Additional Context

- Matrix builds (for example PyO3 wheels for several platforms) need a per-channel matrix hook. Define the contract (`just dist-<channel>` plus an optional matrix declaration) and keep v1 to a single-runner build.
- The seal (#1777) pins this workflow as the expected signer.

### Impact

A single owner of "what is on the Release". It unblocks PyPI byte identity and gives the binaries lane a common base.

### Changelog Category

Added

Refs: #1769, #1770

