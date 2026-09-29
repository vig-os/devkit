---
rfc: ADR-publish-lanes
date: 2026-09-29
title: Turnkey publish lanes — one managed top-level publish workflow, repo-owned builds
status: proposed
authors:
  - Lars Gerchow (gerchowl)
---

# ADR: Turnkey publish lanes per channel

**Decision (TL;DR):** A consumer **declares** the registries it publishes to
(`DEVKIT_PUBLISH=pypi,crates,npm`), and devkit **manages** the publish
mechanics in **one fixed-name, top-level `publish-release.yml`**. The file has
one job per declared channel, and each job's body is a devkit-owned
**composite action**. The **build** stays repo-owned (`just dist-*` recipes).
The filename `publish-release.yml` is **frozen forever**, because registry
Trusted Publishing binds to it.

Around that core:

- **Release assets:** before promote undrafts a Release, a managed **release
  seal** in `promote-release.yml` checks that every asset is attested and adds
  an attested `SHA256SUMS`.
- **OCI images:** the one channel that uses a devkit **reusable** workflow,
  because no registry Trusted Publishing is involved.
- **Nix caches:** reclassified as **CI infrastructure**, not a publish channel.

Decided in spike [#1769](https://github.com/vig-os/devkit/issues/1769) from
eight independent specialist reviews (per-channel findings with primary
sources on #1770–#1776).

## Problem statement

The release train owns the tag and a draft GitHub Release
([#1746](https://github.com/vig-os/devkit/issues/1746)). Everything published
*elsewhere* is left to each repo:

- `release-extension.yml`, `publish-release-extension.yml` and the cargo-dist
  recipe in `docs/DOWNSTREAM_RELEASE.md` are seeded no-ops or copy-paste docs.
- scitadel hand-wrote five workflows
  ([scitadel#208](https://github.com/vig-os/scitadel/pull/208)), tessera would
  rediscover them, and npm has nothing at all.
- Seeded files are repo-owned forever, so a security fix to a publish path
  never reaches consumers through `devkit-upgrade`.

Consumer Releases carry no checksums, SBOM or attestations. devkit's *own*
image release (cosign, SPDX SBOM, build provenance, trusted Cachix push)
already meets the 2026 bar, but consumers get none of it.

The goal is that adopting a channel is **"declare + one-time registry
registration"**, not "copy a recipe and maintain it forever".

## The constraint that shapes everything

crates.io, PyPI and npm **Trusted Publishing** (OIDC, no long-lived tokens)
bind the trusted publisher to the **top-level caller workflow filename** in the
consumer repo. None of them accepts a reusable workflow as the publisher:

- crates.io reads `workflow_ref`, never `job_workflow_ref`
  ([RFC 3691](https://rust-lang.github.io/rfcs/3691-trusted-publishing-cratesio.html)).
- PyPI's publish action refuses reusable callers
  ([gh-action-pypi-publish#166](https://github.com/pypa/gh-action-pypi-publish/issues/166),
  [warehouse#11096](https://github.com/pypi/warehouse/issues/11096)).
- npm matches the caller filename and returns a silent 404 otherwise
  ([npm docs](https://docs.npmjs.com/trusted-publishers/)).

Consequences:

1. A devkit-managed registry lane **must be a top-level file in each consumer
   repo**. It cannot be a reusable workflow hosted in devkit.
2. That filename is registered by hand at every registry, for every package,
   in every consumer. **Renaming it silently breaks all of them**, and
   `devkit-upgrade` cannot re-register. The name is a forever contract.
3. Composite actions do **not** change the caller's OIDC identity. They are
   the only way to centralise the logic and stay OIDC-valid.

## Decision

### 1. One managed `publish-release.yml`

- **Location:** `assets/workspace/.github/workflows/publish-release.yml`,
  **managed** (regenerated on upgrade).
- **Triggers:** `release: published`, which fires because promote publishes
  with the Release App token. Also `workflow_dispatch` with inputs `tag` and an
  optional `channel` for retries.
- **Shared `resolve` job:** proves the Release is published, the same check
  `publish-release-extension.yml` performs today.
- **Channel jobs:** one per channel, gated on `DEVKIT_PUBLISH`. Each job body
  is a devkit composite action.
- **Idempotency:** every job skips a version the registry already has, so a
  re-dispatch after a partial failure finishes the job.
- **Environments:** each channel job runs in an environment (`pypi`,
  `crates-io`, `npm`) with **no required reviewers**, restricted by a
  deployment rule to tag refs. This gives registries an OIDC `environment`
  claim to bind against without adding a second human approval (the
  single-approval rule in `docs/RELEASE_CYCLE.md`). Whether the scaffold can
  assert these environments through the API is still to be probed
  ([#1778](https://github.com/vig-os/devkit/issues/1778)).

**The filename is frozen by this ADR.** The file must never receive a
breaking change. A `publish-preflight` step fails closed when the file and the
declaration disagree.

### 2. The `DEVKIT_PUBLISH` declaration

- **Contract:** the same as `DEVKIT_LANGUAGES`. It is a *declaration* the
  scaffold seeds from evidence, never a detection cache. Undeclared channels
  ship nothing ([#1519](https://github.com/vig-os/devkit/issues/1519)).
- **Evidence:**

  | Channel | Seeded when |
  |---|---|
  | `pypi` | `pyproject.toml` with `[build-system]` |
  | `crates` | a `Cargo.toml` member without `publish = false` |
  | `npm` | `package.json` without `"private": true` |

- **Removing a channel** drops its job. **The file stays.** The scaffold warns
  and links the registry's revoke UI, because devkit cannot de-register a
  trusted publisher.
- **Adoption over a hand-written `publish-release-extension.yml`:** the
  managed file is scaffolded *alongside* it. The repo-owned file is never
  rewritten. The preflight fails if both publish the same channel.

### 3. Ownership split

| | devkit **manages** | devkit **seeds** | repo **owns** |
|---|---|---|---|
| Registry channels | `publish-release.yml`, channel composites, idempotency, prerelease routing, version-spelling mapper | `just dist-*` recipe, registry config stubs | build, versions/metadata, **one-time registry registration**, first manual publish where required |
| Release assets | seal in `promote-release.yml` | — | asset build + its own provenance attestation |
| OCI | reusable publish workflow | thin caller, cleanup, admission-policy example | image name, arches, Dockerfile / flake target |
| Binaries | tag-push asset builder into the draft | `dist-workspace.toml`, signing / tap config | targets, certificates, tap repo |
| Nix (CI infra) | trusted release-cache push | CI cache, `nixConfig` substituters | flake outputs, cache registration |

### 4. Release seal

The seal is the first job of `promote-release.yml`.

- **Why promote:** a human dispatches promote once all assets are on the
  draft, so it is the natural fan-in point. Nothing else signals that "all
  assets are uploaded".
- **Gate:** asset producers attest their own build outputs. The seal
  **refuses to undraft** a Release that has an asset with no attestation.
- **Sums:** it then writes, uploads and attests `SHA256SUMS`, plus an SBOM
  attestation when the repo provides `just sbom`. The format is declared in
  `.vig-os`, SPDX by default.
- **Preflight:** it warns when immutable releases or a tag ruleset are
  missing.
- **No assets:** the seal is a no-op, so tag-only repos are unchanged.
  ([#1777](https://github.com/vig-os/devkit/issues/1777))

### 5. Per-channel verdicts (verified 2026-09-29)

| Channel | Mechanism | Prereleases |
|---|---|---|
| GitHub Release | draft-first train (#1746) + seal | draft pre-release when `create-release: true` |
| crates.io | `crates-io-auth-action`, `cargo publish --workspace` + index precheck, advisory `cargo-semver-checks` | **off** by default (permanent, never resolved by `^`); opt-in with dotted `rc.N` |
| PyPI | `pypa/gh-action-pypi-publish` (PEP 740 attestations; `uv publish` does not attest); maturin-action for PyO3; publishes the same bytes attached to the Release | **on**, production prereleases (`1.2.3rc1`), not TestPyPI |
| npm | Trusted Publishing (CLI >= 11.5.2, Node >= 22.14), automatic provenance, `npm audit signatures` | **on**, `--tag next`; never `latest` |
| OCI | devkit **reusable** workflow: native amd64/arm64, cosign **and** GitHub provenance + SBOM attestations as referrers | `X.Y.Z-rcN` tags pruned on promote; floating tags only after publish |
| Binaries | cargo-dist as asset builder into the draft; managed part shrinks once [cargo-dist#2521](https://github.com/axodotdev/cargo-dist/pull/2521) lands | only when the draft exists |
| GitHub Action | `dist/` freshness at prepare time; floating major tags after publish | — |
| Nix | **CI infrastructure**: per-repo CI cache + trusted release-cache push (Cachix) in the pre-publish window; no FlakeHub | n/a |

**Why OCI is the exception:** no registry Trusted Publishing is involved, and
Fulcio binds the cosign identity to the *called* workflow's `job_workflow_ref`.
A devkit reusable workflow therefore gives every consumer one stable verifier
identity for admission policies. **That reusable path is frozen by this ADR on
the same terms as `publish-release.yml`.**

### 6. Version spelling

A single mapper turns the train version into each channel's spelling:

- SemVer for crates.io, npm and OCI;
- PEP 440 for PyPI;
- an npm dist-tag.

When `pypi` is declared, the mapper **refuses** `DEVKIT_PRERELEASE_FORMAT`
values that PEP 440 cannot express, such as `nightly.{YYYYMMDD}.{N}` or a bare
`beta`.

## Alternatives considered

- **One managed file per channel** (`publish-pypi.yml`, …): rejected. It
  creates N forever-contract filenames instead of one, and each rename is
  unrecoverable across every consumer.
- **Managed reusable workflows called from a seeded top-level file:** rejected
  for registries, which bind the caller filename, not `job_workflow_ref`.
  Accepted only for OCI (§5).
- **Keep extending the seeded `publish-release-extension.yml`:** rejected.
  Fixes never propagate, which repeats the scitadel#208 problem.
- **Seal at tag time in `release-publish.yml`:** rejected. Assets arrive later
  from several workflows, so the sums would be stale.
- **`environment:` with required reviewers:** rejected. It adds a second human
  approval to every release.
- **release-plz / cargo-release as the crates.io engine:** rejected as a
  dependency, because they own prepare→tag→publish and collide with the train.
  They remain a documented opt-out.
- **FlakeHub flake publishing / FlakeHub Cache:** rejected as lock-in.
  `github:` refs against train tags already work.

## Consequences

- **Biggest risk:** the managed filename becomes an org-wide single point of
  failure. Mitigations: this ADR freezes it; `publish-preflight` fails closed;
  no breaking change may touch the file.
- **Adoption keeps unavoidable manual steps:**
  - registering the trusted publisher at each registry;
  - the first publish of each crate and npm package (only PyPI has pending
    publishers);
  - a staged first publish for greenfield Rust workspaces with more than 5 new
    crates, which hit crates.io's new-crate rate limit.

  The runbook must say so up front.
- **New token scopes:** `artifact-metadata: write` (needed by `actions/attest*`
  v4+) joins the seal and OCI grants. GHCR release-candidate pruning needs
  `packages: admin`.
- **Irreversibility:** registry publishes happen only after
  `release: published`, which is the point of no return. A draft stays
  abandonable (`abandon-release.yml`).

## Implementation

Tracked as sub-issues of the channel spikes, in dependency order:

1. [#1777](https://github.com/vig-os/devkit/issues/1777) release seal
2. [#1778](https://github.com/vig-os/devkit/issues/1778) `publish-release.yml`
   skeleton + `DEVKIT_PUBLISH` + environment probe
3. [#1779](https://github.com/vig-os/devkit/issues/1779) PyPI ·
   [#1748](https://github.com/vig-os/devkit/issues/1748) crates.io (now
   managed)
4. [#1780](https://github.com/vig-os/devkit/issues/1780) OCI
5. [#1781](https://github.com/vig-os/devkit/issues/1781) npm ·
   [#1782](https://github.com/vig-os/devkit/issues/1782) GitHub Action
6. [#1783](https://github.com/vig-os/devkit/issues/1783) binaries
7. [#1784](https://github.com/vig-os/devkit/issues/1784) Nix CI / release
   cache
