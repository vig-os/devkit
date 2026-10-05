---
type: issue
state: closed
created: 2026-09-29T15:36:28Z
updated: 2026-09-30T17:51:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1770
comments: 2
labels: discussion, area:workflow
assignees: none
milestone: none
projects: none
parent: 1769
children: 1777, 1786
synced: 2026-10-01T08:40:55.987Z
---

# [Issue 1770]: [[SPIKE] Publish lane: GitHub Releases & release assets (checksums, SBOM, attestations, immutability)](https://github.com/vig-os/devkit/issues/1770)

Parent spike: #1769. Research what a 2026 best-practice GitHub Release looks like beyond "tag + notes", and what devkit should ship to every repo vs. per declared channel.

## Motivation / why

The GitHub Release is the one channel devkit fully manages — but consumers get only tag + CHANGELOG notes. devkit's own release attaches SBOM + provenance for its image; consumer releases carry no checksums, no SBOM, no attestations, so downstream verification (`gh attestation verify`, `sha256sum -c`) is impossible.

## Proposed approach (strawman)

- Keep the managed draft-first flow (#1746). Add an opt-in managed "release assets" step in the pre-publish window: `SHA256SUMS` over all uploaded assets, `actions/attest-build-provenance` (or its 2026 successor) for every asset, optional SBOM.
- Release immutability + tag rulesets as the documented default posture (already in `docs/RELEASE_CYCLE.md`) — verify whether it can be asserted/enabled by the scaffold.

## What already exists

`assets/workspace/.github/workflows/release-publish.yml` (managed; draft-first on `dev`), `promote-release.yml` (only undrafter), `abandon-release.yml`, floating tags (`DEVKIT_FLOATING_TAGS`), upstream `release.yml` SBOM/attest steps.

## Scope / questions

- [ ] Are artifact attestations + checksums table stakes in 2026? Sigstore bundle vs. GitHub attestation store — which do verifiers expect?
- [ ] Checksums: who generates them when assets come from several workflows (cargo-dist + wheel builder) into one draft?
- [ ] Release notes: CHANGELOG extract vs. generated notes — is the current approach still best practice?
- [ ] Can the scaffold enable immutable releases / tag rulesets, or only verify and warn?

## Pitfalls

- Late-landing assets after checksums are computed → stale `SHA256SUMS`; the checksum step must run last, right before promote.
- Immutable releases reject uploads after publish (`HTTP 422`) — every asset step must finish inside the window.
- Attestations need `id-token: write` + `attestations: write`; ceiling interplay with #1144.

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
A 2026 best-practice Release carries **per-asset build provenance in GitHub's attestation store** (not sidecar files), an **SBOM attestation** (SPDX default), a **`SHA256SUMS`** with one attestation over it (goreleaser's `subject-checksums` pattern), **Immutable Releases** (GA 2025-10-28) and a **tag ruleset**. This clears SLSA v1.0 Build L2. L3 requires the signing job to live in an isolated workflow, separate from the build.

## Gap
`release-publish.yml` ships tag + notes only: no sums, SBOM, attestations or ruleset assertion. Upstream `release.yml` already has the pattern for its image. The pre-publish assets window between `release-extension.yml` (can't upload) and `publish-release-extension.yml` (Release already immutable) is the only correct home, and today it is empty.

## Split
- **Managed:** a "seal" step after the last asset lands and **before promote**. It writes `SHA256SUMS`, attests it, and attests the SBOM from a repo `just sbom` recipe. It also runs a ruleset + immutable-releases preflight (enforce or warn) and pins `gh attestation verify` (gh >= 2.49) in the summary.
- **Seeded:** the existing extension seams.
- **Repo:** `just dist-*`, `just sbom`, Trusted Publishing registrations, and any tag-push asset workflows.

## New pitfalls
- **No fan-in signal:** nothing says "all assets are uploaded", so the sums step cannot run at tag time. It needs an explicit gate, and must be a blocking gate before promote rather than a best-effort tail.
- Immutable Releases lock assets and tag, **not release notes**.
- `actions/attest*` v4+ needs `attestations: write` **and** `artifact-metadata: write`.
- The SBOM format choice belongs in `.vig-os`, not in the managed workflow.

Sources: [attest-build-provenance](https://github.com/actions/attest-build-provenance) · [offline verify](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/verifying-attestations-offline) · [goreleaser attestations](https://goreleaser.com/customization/attestations/) · [Immutable releases GA](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/) · [SLSA L3 w/ attestations](https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/) · [rulesets REST](https://docs.github.com/en/rest/repos/rules)


---

# [Comment #2]() by [c-vigo]()

_Posted on September 30, 2026 at 05:51 PM_

Spike complete. The dated verdict is in the review above; the cross-cutting decision is recorded in `docs/rfcs/ADR-publish-lanes.md` (PR #1785, merged to `dev` as 36e74ccc), per #1769's rule that the channel spikes close when the ADR lands.

Implementation continues in: #1777 (release seal), #1786 (release asset builder), #1782 (GitHub Action lane) (lane foundation: #1778).

