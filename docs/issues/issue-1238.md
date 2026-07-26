---
type: issue
state: closed
created: 2026-07-21T09:25:00Z
updated: 2026-07-21T10:57:18Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1238
comments: 1
labels: chore, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:37.808Z
---

# [Issue 1238]: [[CHORE] Automated GHCR cleanup of stale devcontainer package versions](https://github.com/vig-os/devkit/issues/1238)

## Problem

The GHCR package [`vig-os/devcontainer` versions page](https://github.com/vig-os/devkit/pkgs/container/devcontainer/versions) currently holds **587 versions, 487 of which are untagged `sha256:…` orphans**, and it grows by ~5–8 orphans per dev push / RC cycle. The listing is effectively unusable.

### Where the orphans come from (diagnosed 2026-07-21)

1. **`nix-dev` discovery churn** — `nix-image.yml` runs on every push to `dev`/epic branches and re-points the mutable `nix-dev`, `nix-dev-amd64`, `nix-dev-arm64` tags. Each push orphans the previous 3 digests (index + 2 arch manifests). This is the bulk of the 487.
2. **Attestation referrers** — `release.yml` pushes build-provenance + SBOM attestations with `push-to-registry: true` (`actions/attest-build-provenance` / `attest-sbom`). These land as *untagged* OCI referrer manifests (`application/vnd.dev.sigstore.bundle.v0.3+json` with a `subject` pointing at the image digest), ~3 per publish. The ones attached to **kept releases must be preserved** (OCI-native SBOM/provenance verification); the rest are dead.
3. **RC prune leaves referrer orphans** — the `promote-release.yml` cleanup pass (`select-ghcr-prune-targets.sh`) deletes RC image versions and RC cosign `sha256-*` signature *tags*, but not the untagged attestation referrers of those pruned digests. Confirmed live: attestation manifests whose subject digest no longer exists in the registry.

Storage is free (public package), so this is hygiene/usability — but it should be automated, not a one-off manual purge.

## Scope

Add a scheduled bespoke workflow `.github/workflows/ghcr-cleanup.yml` (weekly cron + `workflow_dispatch` with a `dry-run` input) that deletes stale versions of the `vig-os/devcontainer` package using a **referrer/multi-arch-aware** cleanup action ([`dataaxiom/ghcr-cleanup-action`](https://github.com/dataaxiom/ghcr-cleanup-action), pinned by SHA):

- `delete-untagged: true` — removes old `nix-dev` generations and orphaned attestation referrers, while preserving platform children of tagged indexes and attestation/cosign referrers attached to kept (tagged) images.
- `older-than` guard (e.g. 7 days) so in-flight artifacts survive.
- `validate: true` to check multi-arch manifest integrity.
- Same GitHub App token pattern as the existing `promote-release.yml` GHCR prune (org package deletion needs package admin).

The recurring sweep also reclaims the RC attestation-referrer orphans from (3), so extending `select-ghcr-prune-targets.sh` with registry referrer queries is **out of scope** (YAGNI — the sweep covers it within a week).

## Acceptance criteria

- [ ] Dry-run evidence (before merge, via local run of the pinned action, or post-merge dispatch) showing: release-version tags, `latest`, current `nix-dev*`, cosign `sha256-*` signature tags, and attestation referrers of kept releases are **not** selected for deletion.
- [ ] Untagged `nix-dev` orphans and dangling attestation referrers are selected/deleted.
- [ ] Workflow passes actionlint + zizmor gates.
- [ ] ~~`CHANGELOG.md` Unreleased entry~~ — dropped: per repo changelog rules `ci`-internal changes get no entry (matches precedent, e.g. zizmor gate #1185).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 10:57 AM_

Shipped in PR #1239 (merged to `dev` @ bfb458fa, CI fully green).

**Final dry-run evidence — exact merged configuration** (`delete-untagged` + `delete-orphaned-images` + `older-than: 7 days` + `validate`, action v1.2.2 @ `d52806a0` run locally against the live package, `dry-run=true`):

- **364 versions would be deleted** (140 multi-arch groups) out of 587.
- **Keep-safety PASS**: zero live tagged versions in the delete set. Spot-checked absent: `1.4.0`/`latest` index (`c86dcf04`), its attestation referrers (`f653576b`, `63cefef6`, `144e5bce`, referrer-tag index `469bbf68`), `1.3.1` (`9c7b804c`), `1.3.0` (`71ce473d`). Platform children of tagged indexes logged as "skipping … in use by another image".
- The only tagged deletions are two orphaned `sha256-*` referrer tags (`sha256-b8435ba5…`, `sha256-7e524a3e…`) whose parent images no longer exist — intended `delete-orphaned-images` behavior.
- Dangling attestation manifests (e.g. `89e558cd`, subject pruned with its RC) are in the delete set, as required.
- `validate`: warnings only (the dangling-referrer debt this sweep removes), 0 errors.

**Operational note**: `workflow_dispatch` against `dev` returns 404 — GitHub only dispatches workflows present on the **default branch**, and the cron likewise runs from `main` only. The workflow therefore goes live with the **1.4.1 promotion**; a live dispatch dry-run can be exercised right after promote as a final check before the first Monday 04:00 UTC run. Until then the local dry-run above stands as the verification evidence.

All acceptance criteria met (actionlint via pre-commit + CI Project Checks; zizmor N/A — devkit-only workflow outside the managed-scaffold audit scope; changelog dropped per repo `ci`-internal rule).

