---
type: issue
state: open
created: 2026-09-29T15:36:43Z
updated: 2026-09-29T15:41:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1775
comments: 1
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1780
synced: 2026-09-30T08:17:41.562Z
---

# [Issue 1775]: [[SPIKE] Publish lane: OCI images / GHCR (cosign, SBOM, provenance, floating tags)](https://github.com/vig-os/devkit/issues/1775)

Parent spike: #1769. Research the 2026 best practice for publishing OCI container images (GHCR first) and decide what devkit manages for consumers.

## Motivation / why

devkit's own release already does the 2026 bar for its image — cosign keyless signing, SPDX SBOM, build-provenance attestation, RC cleanup (`ghcr-cleanup.yml`) — but consumers get only a minimal "GHCR Publishing" example in `docs/DOWNSTREAM_RELEASE.md`. Every consumer that ships an image re-derives what upstream already solved.

## Proposed approach (strawman)

- Extract the upstream image publish logic into a managed consumer lane: build (project recipe: Dockerfile/Buildah or nix `dockerTools`), push by digest in the pre-publish window, cosign sign + SBOM + provenance attest, then move floating tags (`X`, `X.Y`, `latest`) only after `release: published`.
- RC images tagged `X.Y.Z-rcN`, pruned on promote (as upstream does).

## What already exists

Upstream `.github/workflows/release.yml` (cosign, anchore SBOM, `attest-build-provenance`), `ghcr-cleanup.yml`, `nix-image.yml`, `release-extension.yml` token ceiling includes `packages:write`, floating tags logic (#1626).

## Scope / questions

- [ ] cosign keyless vs. GitHub artifact attestations for images — both, one, which do Kubernetes admission policies (Kyverno/sigstore policy-controller) verify in 2026?
- [ ] SBOM format and attachment (OCI referrers vs. attestation predicate).
- [ ] Multi-arch: native arm64 runners vs. QEMU vs. nix — default?
- [ ] Pushing to other registries (Docker Hub, Quay, ECR) — declared mirrors or out of scope? (cf. #1754 mirror-target seam)
- [ ] Can the upstream implementation be shared (one managed composite) without the upstream-only bits (cross-repo gate)?

## Pitfalls

- Moving `latest` before the Release is published makes an unpromoted image the default.
- Package visibility/permissions on first GHCR push (org-level package settings).
- RC pruning needs package-admin rights (`docs/RELEASE_CYCLE.md` "Registry and cleanup tokens").

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
**Ship both** a cosign keyless signature and GitHub provenance + SBOM attestations, pushed as OCI referrers on the multi-arch digest. Kyverno and the sigstore policy-controller verify both formats. `push-to-registry` has been reported to report success without actually writing the referrer ([sbomify#1530](https://github.com/sbomify/sbomify/issues/1530)), so cosign is the backstop.

## Choices
- **SBOM:** SPDX 2.3 via `anchore/sbom-action` + `actions/attest`. **Not BuildKit `sbom: true`**: that produces index children with no OIDC signer, invisible to `gh attestation verify`. Upstream already does this correctly.
- **Multi-arch:** native `ubuntu-24.04` + `ubuntu-24.04-arm` runners (arm64 standard runners have been in private repos since 2026-01-29), push by digest, then `imagetools create`. No QEMU.
- **Floating tags** (`latest`, `X`, `X.Y`) move **only after `release: published`**. Immutable Releases do not lock GHCR tags, so workflow discipline is the only enforcement.
- **Unlike the registry channels, this lane can be a devkit reusable workflow.** No registry Trusted Publishing is involved, and Fulcio binds the cosign identity to the *called* workflow's `job_workflow_ref`, so the reusable workflow's path becomes the verifier identity. That path is a forever contract for every admission policy.

## Split
- **Managed (reusable):** per-arch build, digest merge, cosign, provenance + SBOM attestations, release-candidate pruning on promote, floating-tag moves.
- **Seeded:** a thin caller workflow, `ghcr-cleanup.yml`, and an example admission policy.
- **Repo:** image name, arches, Dockerfile or flake target, image tests, package visibility.
- **Stays upstream-only:** the cross-repo smoke gate, devkit's own devcontainer publish path, and the org-scoped package-admin token.

## New pitfalls
- Attestations need the containerd image store or the `docker-container` driver; the classic store drops them silently.
- Attestations also need `attestations: write` + `artifact-metadata: write`.
- Release-candidate pruning needs **`packages: admin`**, not `write`.

Sources: [Kyverno sigstore](https://kyverno.io/docs/policy-types/cluster-policy/verify-images/sigstore/) · [GH admission controller](https://docs.github.com/en/actions/security-guides/enforcing-artifact-attestations-with-a-kubernetes-admission-controller) · [use artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) · [Docker attestations](https://docs.docker.com/build/metadata/attestations/) · [arm64 private runners](https://github.blog/changelog/2026-01-29-arm64-standard-runners-are-now-available-in-private-repositories/) · [OIDC + reusable workflows](https://docs.github.com/actions/deployment/security-hardening-your-deployments/using-openid-connect-with-reusable-workflows)


