---
type: issue
state: open
created: 2026-09-29T15:45:22Z
updated: 2026-09-29T15:53:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1780
comments: 1
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1775
children: none
synced: 2026-09-30T08:17:38.945Z
---

# [Issue 1780]: [[FEATURE] OCI publish lane: managed reusable GHCR workflow (multi-arch, cosign, provenance, SBOM)](https://github.com/vig-os/devkit/issues/1780)

### Description

Implementation of the OCI/GHCR channel for the publish-lane spike #1769 (review on #1775). Extract upstream's image publishing into a devkit-managed **reusable** workflow that consumers call.

### Problem Statement

Upstream `.github/workflows/release.yml` already meets the 2026 standard: cosign keyless signing, an SPDX SBOM, provenance attestation, and RC pruning. Consumers get only a minimal example in `docs/DOWNSTREAM_RELEASE.md`.

### Proposed Solution

- **Managed reusable workflow:**
  - builds each architecture on native `ubuntu-24.04` and `ubuntu-24.04-arm` runners, pushes by digest, and merges with `imagetools create`;
  - signs with cosign and attests provenance and SBOM (`anchore/sbom-action` + `actions/attest`, pushed to the registry);
  - prunes release-candidate images on promote;
  - moves the floating tags (`latest`, `X`, `X.Y`) **only after `release: published`**.
- **An exception to the top-level-file rule:** no registry Trusted Publishing is involved, and cosign binds its identity to the called workflow's path, so devkit's reusable path becomes the stable verifier identity. That path is frozen in the ADR.
- **Seeded:** a thin caller, `ghcr-cleanup.yml`, and an example admission policy (Kyverno or policy-controller).
- **Repo-owned:** image name, architectures, and the build recipe (Dockerfile or flake target).
- **Stays upstream-only:** the cross-repo smoke gate, devkit's own devcontainer path, and the org package-admin token.

### Alternatives Considered

BuildKit `sbom: true` (not a GitHub attestation); QEMU multi-arch (slow, and drops attestations); cosign-only or attestations-only (verifiers differ; `push-to-registry` has been reported to report success without writing the referrer).

### Additional Context

Needs the containerd image store or the `docker-container` driver; `artifact-metadata: write`; `packages: admin` for pruning.

### Impact

Image-shipping repos get the same supply-chain posture as devkit's own image.

### Changelog Category

Added

Refs: #1769, #1775

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:53 PM_

**Revised after the ADR review on PR #1785** (`docs/rfcs/ADR-publish-lanes.md`):
- **Release-candidate images are deferred to #1787.** v1 publishes finals only, and floating tags still move only after `release: published`.
- **Candidate-image pruning** is a declaration-gated step in managed `promote-release.yml`'s existing `cleanup` job, not in the reusable workflow.
- Pruning needs a **package admin grant** on the GHCR package, not a `GITHUB_TOKEN` scope (`packages: admin` does not exist); see "Registry and cleanup tokens" in `docs/RELEASE_CYCLE.md`.
- The reusable workflow's path is **frozen** in the ADR (it is the cosign verifier identity).

