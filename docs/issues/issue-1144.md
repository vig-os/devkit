---
type: issue
state: closed
created: 2026-07-15T21:03:06Z
updated: 2026-07-16T11:50:51Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1144
comments: 1
labels: feature, priority:low, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:03.948Z
---

# [Issue 1144]: [[FEATURE] release-extension seam: GITHUB_TOKEN ceiling blocks id-token/attestations (provenance attestation cannot live in the extension point)](https://github.com/vig-os/devkit/issues/1144)

### Description

The managed `release.yml` calls the `release-extension.yml` consumer seam with no job-level `permissions:` block, so the called workflow runs under the caller's workflow-level grant (`contents: read, packages: read`). GitHub never lets a called reusable workflow ELEVATE the caller's `GITHUB_TOKEN` — job-level permissions in the callee can only downgrade.

Consequence: any extension step needing more than read (e.g. `actions/attest-build-provenance`, which requires `id-token: write` + `attestations: write`) is silently denied. Found while porting sync-issues-action's provenance attestation into the seam during its devkit adoption (vig-os/sync-issues-action#106) — the attestation had to be re-homed in a consumer-owned tag-push workflow (`attest-release.yml`) instead, where the job owns its token grant.

### Acceptance Criteria

- [ ] Decide the seam's permission contract: either grant the extension job a documented broader ceiling (e.g. add `id-token: write`, `attestations: write` — still deny-by-default at the callee), or explicitly document that write-scoped extensions belong in consumer-owned tag-push/post-release workflows
- [ ] Document the pattern in the release extension docs either way

### Additional Context

- The seam grant lives in the managed `release.yml` `extension:` job (no `permissions:` → workflow default applies).
- Workaround shipping in sync-issues-action: `attest-release.yml` on `push: tags: v*.*.*` with its own `id-token: write` + `attestations: write` grant.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 11:50 AM_

Resolved on `dev` via #1148 (merge commit 557add06) — option A. The scaffolded `release.yml` `extension` caller job now grants the seam a documented token ceiling (`contents: read`, `packages: write`, `id-token: write`, `attestations: write`); ceiling-not-grant, default no-op stays read-only, consumers opt in per job. Documented in `docs/DOWNSTREAM_RELEASE.md`. Ships with the next devkit release.

