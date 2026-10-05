---
type: issue
state: open
created: 2026-09-29T15:45:12Z
updated: 2026-09-29T15:53:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1777
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1770
children: none
synced: 2026-09-30T08:17:40.520Z
---

# [Issue 1777]: [[FEATURE] Release seal: SHA256SUMS + attestation gate in promote-release before undrafting](https://github.com/vig-os/devkit/issues/1777)

### Description

Implementation of the **release seal** from `docs/rfcs/ADR-publish-lanes.md` §4 (spike #1769, channel review on #1770). Before `promote-release.yml` undrafts a Release, the seal **verifies** each asset's build-provenance attestation, then uploads and attests a `SHA256SUMS` covering all assets.

*Revised after the ADR review on PR #1785. The earlier draft gated on an attestation merely existing, ran before `validate`, and omitted the App token and private-repo handling.*

### Problem Statement

Consumer releases carry no checksums, SBOM or attestations, so downstream verification (`gh attestation verify`, `sha256sum -c`) is impossible. Assets arrive from several workflows in the pre-publish window: the asset builder (#1786), cargo-dist (#1783), and repo-owned workflows. Nothing marks the point where "all assets are uploaded", so sums computed at tag time would be stale.

### Proposed Solution

- **Placement:** a new `seal` job in managed `assets/workspace/.github/workflows/promote-release.yml`, in the order **`validate → seal → promote`**. It runs only after approval, CI and mergeability have been validated, and before the draft is undrafted.
- **Gate, which verifies rather than checking presence:**
  - For every asset (except the seal's own files), run `gh attestation verify` with this repo as signer, requiring the SLSA provenance predicate.
  - For assets from the asset builder, also pin `--signer-workflow` to `release-assets.yml`.
  - Any failure **blocks the undraft**.
- **Sums:**
  - Write `SHA256SUMS` and upload it with the **Release App token**; promote's existing writes already use it (`promote-release.yml` token step).
  - Create **one** `actions/attest-build-provenance` attestation with `subject-checksums: SHA256SUMS`. Its subjects are the listed assets; it does not attest the checksum file itself.
  - Add an SBOM attestation (`actions/attest-sbom`) when the repo has a `just sbom` recipe. The format comes from `.vig-os`, SPDX by default.
- **Degrade mode:** `.vig-os` `DEVKIT_RELEASE_SEAL=auto|verify|sums|off`, default `auto`.
  - Artifact attestations need a **public repo, or GitHub Enterprise Cloud** for private and internal repos.
  - `auto` verifies and attests when attestations are available. Otherwise it falls back to `sums` (checksums only) with a warning, so private repos on Free or Team plans can still promote.
- **Preflight:** warn when immutable releases or a tag ruleset are missing. Probe whether the scaffold can enforce them through the API.
- **No assets:** the seal is a no-op, so tag-only repos are unchanged.
- **Docs:** add the verify recipe (`gh attestation verify`, gh >= 2.49) to the job summary and to `docs/DOWNSTREAM_RELEASE.md`.
- **Permissions:** `contents: read`, `id-token: write`, `attestations: write`, `artifact-metadata: write`, plus the App token for uploads.

### Alternatives Considered

- Sums at tag time in `release-publish.yml`: rejected; stale when assets land later.
- Gate on "an attestation exists": rejected; any repo workflow with `attestations: write` could satisfy it.
- Per-tool attestations only (cargo-dist `github-attestations`): rejected; not language-neutral.

### Additional Context

- Immutable releases lock assets and tag **but not notes**. After promote there is no late upload (HTTP 422).
- Upstream reference: the SBOM and attest steps in `.github/workflows/release.yml`.
- Acceptance: tests cover the `validate → seal → promote` ordering, the verification failure path, `auto` falling back to `sums`, and the no-assets no-op.

### Impact

Every consumer that publishes Release assets gets verified, checksummed releases: SLSA Build L2 where attestations are available, checksums everywhere else. Tag-only consumers are unaffected.

### Changelog Category

Added

Refs: #1769, #1770, #1746

