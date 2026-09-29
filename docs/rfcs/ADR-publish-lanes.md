---
rfc: ADR-publish-lanes
date: 2026-09-29
title: Turnkey publish lanes — one managed top-level publish workflow, repo-owned builds
status: proposed
authors:
  - Lars Gerchow (gerchowl)
---

# ADR: Turnkey publish lanes per channel

**Decision (TL;DR):** A consumer **declares** the channels it publishes to
(`DEVKIT_PUBLISH=pypi,crates,npm,oci,binaries`), and devkit **manages** the
publish mechanics. The **build** stays repo-owned (`just dist-*` recipes).

- **Registry channels** (PyPI, crates.io, npm) are jobs in **one fixed-name,
  top-level `publish-release.yml`**. Each job's body is a devkit-owned
  **composite action**. Its filename, job ids and environment names are
  **frozen forever**, because registry Trusted Publishing binds to them.
- **Release assets:** a managed **asset builder** uploads build outputs into
  the train's draft GitHub Release and attests them. A managed **release
  seal** in `promote-release.yml` then verifies those attestations and adds an
  attested `SHA256SUMS` before the draft is undrafted.
- **OCI images** are the one channel that uses a devkit **reusable** workflow,
  because no registry Trusted Publishing is involved.
- **Nix caches** are reclassified as **CI infrastructure**, not a publish
  channel.
- **v1 publishes finals only** to the registries. Candidate publishing needs a
  trigger the train does not have yet, and it is tracked separately.

Decided in spike [#1769](https://github.com/vig-os/devkit/issues/1769) from
eight independent specialist reviews (per-channel findings with primary
sources on #1770–#1776), then revised after a second, adversarial review of
this ADR (see [Revisions after review](#revisions-after-review)).

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
consumer repo, optionally plus a GitHub **environment** name. None of them
accepts a reusable workflow as the publisher:

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
2. That filename, and the environment name if one is registered, are entered
   by hand at every registry, for every package, in every consumer.
   **Renaming either silently breaks all of them**, and `devkit-upgrade`
   cannot re-register. Both are forever contracts.
3. Composite actions do **not** change the caller's OIDC identity. They are
   the only way to centralise the logic and stay OIDC-valid.

## Decision

### 1. One managed `publish-release.yml`

- **Location:** `assets/workspace/.github/workflows/publish-release.yml`,
  **managed** (regenerated on upgrade).
- **Triggers:**
  - `release: published`, which fires because promote publishes with the
    Release App token;
  - `workflow_dispatch` with inputs `tag` and an optional `channel`, for
    retries. A retry is dispatched from the default branch.
- **Shared `resolve` job:** proves the Release is published and is **not** a
  prerelease. That is v1's finals-only rule, enforced in code rather than in
  docs.
- **Channel jobs:** one per registry channel, job ids `pypi`, `crates`, `npm`.
  Each is gated on `DEVKIT_PUBLISH`, and each body is a devkit composite
  action.
- **Idempotency:** every job skips a version the registry already has, so a
  re-dispatch after a partial failure finishes the job.
- **Concurrency:** group `registry-publish-<tag>`. The name `publish-release`
  is **already taken** by `promote-release.yml` and `abandon-release.yml`,
  so it must not be reused.
- **Environments:** frozen names `publish-pypi`, `publish-crates` and
  `publish-npm`. They are deliberately distinct from the `pypi` / `crates-io`
  names the seeded `publish-release-extension.yml` header suggests, so a
  repo's existing reviewer-gated environments are never touched.
  - The scaffold **creates each environment only if it is absent**. It uses
    **no required reviewers** and a deployment-branch policy that allows the
    release tags **and the default branch**, because `workflow_dispatch`
    retries run from the default branch.
  - The scaffold **never modifies an existing environment**. A repo that adds
    reviewers has opted into a second approval, which the single-approval
    rule in `docs/RELEASE_CYCLE.md` otherwise avoids.
  - Whether the scaffold can create these environments through the API
    (rather than documenting them) is probed in
    [#1778](https://github.com/vig-os/devkit/issues/1778).

**Frozen by this ADR:** the filename `publish-release.yml`, the job ids, and
the environment names. None of these may ever receive a breaking change, and a
test pins them (#1778).

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
  | `oci` | a Dockerfile / Containerfile, or a flake image output |
  | `binaries` | `dist-workspace.toml`, or a Cargo `[[bin]]` target |

  Only `pypi`, `crates` and `npm` are jobs in `publish-release.yml`. `oci` and
  `binaries` scaffold their own lanes (§5).
- **Removing a channel** drops its job. **The file stays.** The scaffold warns
  and links the registry's revoke UI, because devkit cannot de-register a
  trusted publisher.
- **Adoption over a hand-written `publish-release-extension.yml`:**
  - The managed file is scaffolded *alongside* it. The repo-owned file is
    never rewritten.
  - The overlap check (both files publishing the same channel) runs **before
    the point of no return**: at scaffold/upgrade time and in promote's
    `validate` job. It is a best-effort grep of the free-form extension file,
    so it warns and does not guarantee.
  - Moving a channel from the extension file to the managed file needs a
    **new registration at the registry**, because the filename changes.

### 3. Ownership split

| | devkit **manages** | devkit **seeds** | repo **owns** |
|---|---|---|---|
| Registry channels | `publish-release.yml`, channel composites, idempotency, finals-only guard, version-spelling mapper | registry config stubs | versions/metadata, **one-time registry registration**, first manual publish where required |
| Release assets | asset builder (tag-push → `just dist-*` → upload + attest into the draft); seal in `promote-release.yml` | `just dist-*` / `just sbom` recipes | the build itself |
| OCI | reusable publish workflow; RC-image prune step in promote | thin caller, cleanup, admission-policy example | image name, arches, Dockerfile / flake target |
| Binaries | cargo-dist runner on top of the asset builder | `dist-workspace.toml`, signing / tap config | targets, certificates, tap repo |
| Nix (CI infra) | trusted release-cache push | CI cache, `nixConfig` substituters | flake outputs, cache registration |

### 4. Asset builder and release seal

**Asset builder (managed, tag-push).**
([#1786](https://github.com/vig-os/devkit/issues/1786))

- For each declared channel that produces files, it runs the repo's
  `just dist-<channel>` and uploads the outputs into the train's draft with
  `--clobber`.
- It attests each output with `actions/attest-build-provenance`.
- When no draft exists (a tag-only candidate), it does nothing.
- PyPI (§5) and binaries build on it. It is the single owner of "the bytes on
  the Release", so a registry job can publish those exact bytes.

**Release seal (managed, in `promote-release.yml`).**
([#1777](https://github.com/vig-os/devkit/issues/1777))

- **Placement:** `validate → seal → promote`. The seal runs only after promote
  has checked approval, CI and mergeability, and before the draft is
  undrafted. Promote is the natural fan-in point, because a human dispatches
  it once all assets are on the draft; nothing else signals that "all assets
  are uploaded".
- **Gate — verification, not mere presence:** for each asset, the seal runs
  `gh attestation verify` against **this repo** as signer, requiring the SLSA
  provenance predicate. Where the signer workflow is known (the asset
  builder), it pins that too. An asset that fails verification **blocks the
  undraft**.
- **Sums:**
  - It writes `SHA256SUMS` and uploads it with the **Release App token**
    (writing to a draft needs it, as promote's other writes do).
  - It creates **one** build-provenance attestation whose subjects are the
    assets listed in `SHA256SUMS` (`subject-checksums`). That attests the
    assets, not the checksum file itself.
  - It adds an SBOM attestation when the repo provides `just sbom`. The
    format is declared in `.vig-os`, SPDX by default.
- **Degrade mode** (`DEVKIT_RELEASE_SEAL=auto|verify|sums|off`, default
  `auto`): artifact attestations need a **public repo, or GitHub Enterprise
  Cloud** for private and internal repos
  ([attest-build-provenance](https://github.com/actions/attest-build-provenance)).
  In `auto` mode, the seal verifies and attests when attestations are
  available, and otherwise falls back to `sums` (checksums only, with a
  warning). Without this, a private consumer on a Free or Team plan could
  never promote.
- **Preflight:** the seal warns when immutable releases or a tag ruleset are
  missing.
- **No assets:** the seal is a no-op, so tag-only repos are unchanged.

### 5. Per-channel verdicts (verified 2026-09-29)

| Channel | Mechanism | v1 prereleases |
|---|---|---|
| GitHub Release | draft-first train (#1746) + asset builder + seal | draft pre-release when `create-release: true` (unchanged) |
| crates.io | `crates-io-auth-action`, `cargo publish --workspace --no-verify` from the tag + index precheck; dry-run gate at the same SHA; advisory `cargo-semver-checks` | none — and off by default even once candidates are supported (permanent, never resolved by `^`) |
| PyPI | `pypa/gh-action-pypi-publish` (PEP 740 attestations; `uv publish` does not attest), uploading **the wheels and sdist that the asset builder put on the Release**; maturin-action for PyO3 | none in v1; target policy is production prereleases (`1.2.3rc1`), not TestPyPI |
| npm | Trusted Publishing (CLI >= 11.5.2, Node >= 22.14), automatic provenance, `npm audit signatures` | none in v1; target policy is `--tag next`, never `latest` |
| OCI | devkit **reusable** workflow: native amd64/arm64, cosign **and** GitHub provenance + SBOM attestations as referrers; floating tags only after publish | none in v1; target policy is `X.Y.Z-rcN` tags pruned on promote |
| Binaries | cargo-dist through the asset builder; the managed part shrinks once [cargo-dist#2521](https://github.com/axodotdev/cargo-dist/pull/2521) lands | only when the draft exists |
| GitHub Action | `dist/` freshness at prepare time; floating major tags after publish | — |
| Nix¹ | per-repo CI cache + trusted release-cache push (Cachix) in the pre-publish window; no FlakeHub | n/a |

¹ **Not a publish channel.** Listed for completeness only. It is not part of
`DEVKIT_PUBLISH`, because the cache only saves bandwidth and never affects
release correctness.

**Byte identity:**

- **PyPI** publishes exactly the bytes on the Release, so the Release
  attestation and the PEP 740 attestation describe the same files.
- **crates.io cannot do this.** `cargo publish` always repackages and cannot
  upload a prebuilt `.crate`. That reverses the spike consolidation's
  "wheel *or crate*, same bytes" pitfall. For crates, publishing from the
  tagged SHA, with the dry-run gate at that same SHA, is the substitute.

**Why OCI is the exception:** no registry Trusted Publishing is involved, and
Fulcio binds the cosign identity to the *called* workflow's `job_workflow_ref`.
A devkit reusable workflow therefore gives every consumer one stable verifier
identity for admission policies.

- **That reusable path is frozen** on the same terms as
  `publish-release.yml`.
- **Candidate-image pruning** runs as a declaration-gated step in managed
  `promote-release.yml`'s existing cleanup job.
- It needs a **package admin grant** on the GHCR package, not a
  `GITHUB_TOKEN` scope (see "Registry and cleanup tokens" in
  `docs/RELEASE_CYCLE.md`).

### 6. Version spelling

A single mapper turns the train version into each channel's spelling:

- SemVer for crates.io, npm and OCI;
- PEP 440 for PyPI;
- an npm dist-tag.

When `pypi` is declared, the mapper **refuses** `DEVKIT_PRERELEASE_FORMAT`
values that PEP 440 cannot express, such as `nightly.{YYYYMMDD}.{N}` or a bare
`beta`. It lands with #1778, because candidate publishing will need it; in v1
it only validates.

### 7. Candidate publishing (deferred)

Registry candidates have **no trigger today**:

- `publish-release.yml` fires on `release: published`, and only promote
  publishes a Release — finals only.
- Candidate draft pre-releases are **deleted** by promote's cleanup job.
- Tag-only candidates have no Release at all.

Candidate publishing therefore needs its own trigger, for example a candidate
path dispatched by `release-core.yml` with the App token and resolved against
the tag rather than a Release. It is tracked in
[#1787](https://github.com/vig-os/devkit/issues/1787). Until it lands, the
`resolve` job refuses prereleases, so nothing irreversible can publish a
candidate by accident.

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
- **Seal gate = "an attestation exists":** rejected. Any workflow in the repo
  holding `attestations: write` could satisfy it; the gate must verify signer
  and predicate.
- **`environment:` with required reviewers, or reusing the `pypi` /
  `crates-io` names:** rejected. It adds a second human approval, or silently
  inherits or strips a repo's own gate.
- **Deployment rule limited to tag refs:** rejected. It breaks
  `workflow_dispatch` retries from the default branch.
- **Candidates on `release: published`:** impossible without changing the
  promote/cleanup lifecycle; see §7.
- **release-plz / cargo-release as the crates.io engine:** rejected as a
  dependency, because they own prepare→tag→publish and collide with the train.
  They remain a documented opt-out.
- **FlakeHub flake publishing / FlakeHub Cache:** rejected as lock-in.
  `github:` refs against train tags already work.

## Consequences

- **Biggest risk:** the frozen names (filename, job ids, environment names,
  the OCI reusable path) become an org-wide single point of failure.
  Mitigations: this ADR freezes them, a test pins them, and no breaking change
  may touch them. A preflight cannot detect drift in what is *registered*,
  because registries do not expose the registered subject. That is why the
  names are frozen rather than monitored.
- **Adoption keeps unavoidable manual steps:**
  - registering the trusted publisher at each registry;
  - the first publish of each crate and npm package (only PyPI has pending
    publishers);
  - a staged first publish for greenfield Rust workspaces with more than 5 new
    crates, which hit crates.io's new-crate rate limit.

  The runbook must say so up front.
- **Private repos** without GitHub Enterprise Cloud get checksums but no
  attestations (seal `auto` falls back to `sums`), and PyPI PEP 740 continuity
  with a Release attestation is then unavailable.
- **New token scopes:** `artifact-metadata: write` (needed by `actions/attest*`
  v4+) joins the asset builder, the seal and OCI.
- **Irreversibility:** registry publishes happen only after
  `release: published`, which is the point of no return. A draft stays
  abandonable (`abandon-release.yml`).

## Implementation

Tracked as sub-issues of the channel spikes. The list below is a **priority
order**. Hard dependencies are set as GitHub "blocked by" links on each issue.

1. [#1786](https://github.com/vig-os/devkit/issues/1786) asset builder ·
   [#1777](https://github.com/vig-os/devkit/issues/1777) release seal
2. [#1778](https://github.com/vig-os/devkit/issues/1778) `publish-release.yml`
   skeleton, `DEVKIT_PUBLISH`, environments, freeze test, docs rewrite
3. [#1779](https://github.com/vig-os/devkit/issues/1779) PyPI ·
   [#1748](https://github.com/vig-os/devkit/issues/1748) crates.io (now
   managed)
4. [#1780](https://github.com/vig-os/devkit/issues/1780) OCI
5. [#1781](https://github.com/vig-os/devkit/issues/1781) npm ·
   [#1782](https://github.com/vig-os/devkit/issues/1782) GitHub Action
6. [#1783](https://github.com/vig-os/devkit/issues/1783) binaries
7. [#1784](https://github.com/vig-os/devkit/issues/1784) Nix CI / release
   cache
8. [#1787](https://github.com/vig-os/devkit/issues/1787) candidate publishing
   (deferred, §7)

## Revisions after review

A fresh-context review of the first draft blocked it on four points. All are
addressed above:

- **Candidates had no trigger.** v1 is now finals only, with a `resolve`
  guard; candidate publishing is deferred to #1787 (§7).
- **The tag-only deployment rule broke retries, and the environment names
  collided with the seeded extension's suggestion.** Environments are now
  newly named, allow the default branch, and are never modified once they
  exist (§1).
- **The seal gated on presence, ran before `validate`, lacked the App token,
  and assumed attestations are available everywhere.** It now verifies signer
  and predicate, runs `validate → seal → promote`, uploads with the App token,
  and has a degrade mode (§4).
- **Nothing owned the PyPI bytes.** A managed asset builder, #1786, now owns
  them (§4).

The review also produced smaller changes: the crate byte-identity reversal is
now explicit, the overlap preflight moved before the point of no return, the
concurrency group is renamed, OCI prune wiring and the package-admin grant are
specified, and the docs rewrite and freeze test have an owner (#1778).
