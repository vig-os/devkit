---
type: issue
state: open
created: 2026-09-28T21:17:18Z
updated: 2026-09-28T21:17:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1754
comments: 0
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:52.884Z
---

# [Issue 1754]: [[FEATURE] Data release lane: CalVer data artefacts on their own tag namespace, with an integrity contract and a mirror-target seam (GH Releases / HF / OCI / DOI)](https://github.com/vig-os/devkit/issues/1754)

### Description

Give the devkit a **second release lane for data artefacts** — an independently-versioned, independently-cadenced artefact stream that rides its own tag namespace, carries a per-file integrity contract, and fans out to mirror targets (GitHub Releases, Hugging Face, OCI/ORAS, DOI) through a consumer-owned seam.

Language-neutral *and* payload-neutral by construction. Every domain-specific mechanism (what the tarball contains, what the catalog file looks like, which licences apply, which shards a mirror wants) stays in consumer files. What the devkit ships is the **state machine and the contract**: file-derived version → one-operation tag → verify gate → signed manifest → draft asset window → mirror fan-out → reconciliation.

Motivating prior art, already written by hand and paid for in production incidents: **[exoma-ch/nucl-parquet](https://github.com/exoma-ch/nucl-parquet)** ships a ~1 GB Parquet dataset on a `data-YYYY.MM.MICRO` CalVer namespace decoupled from its code semver, across three hand-written workflows ([`release-data.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/release-data.yml), [`auto-tag-data.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/auto-tag-data.yml), [`reconcile-data-release.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/reconcile-data-release.yml)). It is **not** a devkit consumer today (no `.vig-os`) — and its data lane is the reason it cannot become one without giving something up.

Sibling of [#1746](https://github.com/vig-os/devkit/issues/1746) (Rust release extension via a general publish/Release-owner seam). That issue generalises the train for a *second language*; this one generalises it for a *second artefact class*. They share section 2 of #1746 (the draft-Release-first "pre-publish assets window"), and this issue is the case that makes that window load-bearing rather than tidy.

### Problem Statement

A devkit consumer gets exactly one release train, and that train is shaped end to end around "a code version, with a changelog, cut on a release branch, approved by a human, promoted once". A data refresh is none of those things. Six concrete refusals:

**1. One repo = one tag namespace, one version model, one concurrency group.**
`DEVKIT_TAG_PREFIX` resolves to a single value ([`resolve-toolchain/action.yml#L169`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/actions/resolve-toolchain/action.yml#L169)), `release.yml` holds `concurrency: group: release`, and the version gate is `^[0-9]+\.[0-9]+\.[0-9]+$` ([`release-core.yml#L176`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L176)). A CalVer string like `2026.8.5` *syntactically passes* that regex — which is worse than being rejected: it would be published under the `v` prefix, share the `## Unreleased` changelog, open a release PR, and consume the cycle's single human approval. A dataset refresh has no changelog freeze, no release branch, and no reason to block on (or be blocked by) a code release.

**2. The version's source of truth is a repo file, not a dispatch input.**
nucl-parquet's SSoT is `data/catalog.json::data_version`, and the trigger is *a merge to main that changes it* — the PR review is the human gate. Every devkit entry point is `workflow_dispatch -f version=X.Y.Z`. There is no "merge-triggered, file-derived version" shape in the train at all, and it is the correct shape for data: the catalog and the release cannot disagree if the catalog is what causes the release.

**3. There is no large-asset window that survives immutable releases.**
`release-publish.yml` creates the tag ref first ([`#L177`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-publish.yml#L177)), then `gh release create … --verify-tag --draft` ([`#L269`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-publish.yml#L269)). Per devkit's own policy ([DOWNSTREAM_RELEASE.md § Immutable releases](https://github.com/vig-os/devkit/blob/main/docs/DOWNSTREAM_RELEASE.md#immutable-releases-tag-rulesets-and-forward-fix-policy)), **publishing** locks the linked tag *and assets*. So a ~1 GB asset — which will need retries — can only be attached during the draft window. nucl-parquet today uploads with `softprops/action-gh-release` onto a release that is created-and-published in one go; **that shape breaks the day the org enables immutable releases**, and it breaks with a 422 after the bytes are already built. This is exactly the failure [vig-os/tessera#440](https://github.com/vig-os/tessera/issues/440) hit from the other direction.

**4. There is no integrity contract for data, and a tarball digest is not one.**
Code gets tags plus provenance attestations (`attestations: write` is already in the extension ceiling). Data needs two things the train has no opinion on:
   - **A per-file manifest, not just an archive digest.** An archive signature stops being verifiable the moment anything legitimately rewrites the archive — which is routine on the way into an isolated network, where Content Disarm & Reconstruction gateways open a `.tar.zst`, scan each entry and repack it. A signed map of per-file digests survives a repack and lets a *partial* transfer be verified. nucl-parquet learned this as [exoma-ch/nucl-parquet#296](https://github.com/exoma-ch/nucl-parquet/issues/296) and enforces tarball-members ≡ manifest-keys as a hard gate, because two individually well-formed artefacts that disagree is a silently unverifiable release.
   - **A publisher signature over both, that hard-fails when absent.** [exoma-ch/nucl-parquet#289](https://github.com/exoma-ch/nucl-parquet/issues/289): an unsigned data release must be *impossible*, not merely unusual, and it must verify against the **committed** public key consumers pin — that is what catches a rotated-but-not-committed key before it ships.

**5. Nothing reconciles the claim against reality.**
"Does the version this repo claims actually exist, complete and signed, as a published release?" is an invariant no shipped lane asserts. nucl-parquet only added [`reconcile-data-release.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/reconcile-data-release.yml) after [exoma-ch/nucl-parquet#344](https://github.com/exoma-ch/nucl-parquet/issues/344) left `data-2026.8.3` tagged with no release, no tarball and no signature, and a catalog claiming a version nobody could download. The generalisable lesson is in that workflow's header: *a check that fails for the same reasons as the thing it checks is not a check*, and **a red scheduled run is itself something nobody looks at** — the detector must open/update/close a labelled tracking issue, and go red only as belt and braces.

**6. Every mirror target is hand-rolled, and silently drifts.**
GitHub Releases is one distribution point; real consumers want lazy per-file fetches, offline/air-gapped pulls, and citable DOIs. nucl-parquet's Hugging Face mirror published ENDF/B-VIII.0 under `license: mit` — a grant nobody there can make over a US Government work ([exoma-ch/nucl-parquet#234](https://github.com/exoma-ch/nucl-parquet/issues/234)) — because the card was maintained by hand. The fix generalises: **the mirror's metadata must be generated from the repo's compliance record on every release**, and the mirror must be gated on a *declared* state, never on whether a secret happens to exist ([exoma-ch/nucl-parquet#283](https://github.com/exoma-ch/nucl-parquet/issues/283) — the job reported green through two releases while pushing nothing; "mirror silently did nothing" must never be indistinguishable from "mirror is current").

Related: [#1746](https://github.com/vig-os/devkit/issues/1746) (shares the draft-Release-first window), [#330](https://github.com/vig-os/devkit/issues/330) (closed — asset handoff only), [#1144](https://github.com/vig-os/devkit/issues/1144) (permission ceiling — why the data lane is standalone, not a called workflow), [#1519](https://github.com/vig-os/devkit/issues/1519) (smallest denominator — this ships contract, not a data pipeline), [#1284](https://github.com/vig-os/devkit/issues/1284) (manifest-driven scaffold feature opt-outs — how the lane is gated), [#1523](https://github.com/vig-os/devkit/issues/1523) (org stack matrix — "data release" is a capability row).

### Proposed Solution

A **second, standalone lane** — not a parameterisation of the code train. Seven parts; the first four are the minimum viable cut.

#### 1. `.vig-os` keys — opt-in, declared

The data lane is **opt-in** (unlike `DEVKIT_FEATURES_DISABLED`, which opts *out* of things every consumer gets):

| Key | Default | Meaning |
| --- | --- | --- |
| `DEVKIT_DATA_RELEASE` | `false` | Enables the lane; scaffolds the workflows. |
| `DEVKIT_DATA_TAG_PREFIX` | `data-` | Second tag namespace, independent of `DEVKIT_TAG_PREFIX`. |
| `DEVKIT_DATA_VERSION_SOURCE` | — | `<path>#<json-pointer>`, e.g. `data/catalog.json#/data_version`. The file shape stays consumer-owned; the devkit only knows how to read one scalar out of it. |
| `DEVKIT_DATA_VERSION_FORMAT` | `calver` | `calver` (`YYYY.MM.MICRO`), `semver`, or `date` (`YYYYMMDD`). Validated; the tag-discovery pattern is **derived** from it, never hard-coded. |

Scaffold-time realisation, same as `DEVKIT_WORKFLOW`/`DEVKIT_LANGUAGES` — no runtime branching on absent config.

#### 2. `release-data.yml` — the lane, triggered by the tag

`on: push: tags: ['<data-prefix>*']` + `workflow_dispatch { tag }` as the documented recovery path. Jobs, in this order:

1. **`verify`** — calls the consumer's own `ci.yml`. **Do not publish bytes the test suite has not passed.** This ordering is the single most important thing to copy: nucl-parquet ran these concurrently and published `data-2026.8.2` *signed* while `Verify clients` was still `in_progress`. It passed by luck. Signing is what makes the gap matter — "these bytes came from the data team" is a much weaker claim if the team's own suite never gated them, and an unverified *signed* release is worse than an unverified unsigned one, because downstream now has a reason to trust it. The cost (a flaky suite blocks a data release) is the right trade for an artefact we cryptographically vouch for.
2. **`validate`** — re-derive the version from `DEVKIT_DATA_VERSION_SOURCE` and assert it equals the tag. Cheap, and it is the whole reason the catalog cannot drift from the release.
3. **`package`** → `release-data-extension.yml` (consumer-owned, mutating, `contents: read` ceiling + the build scopes) — produces the artefact set. **The devkit never learns what the payload is.**
4. **`attest`** — manifest + signature (§4).
5. **`publish`** — draft-first upload into the pre-publish window (§3).
6. **`mirror`** → `release-data-mirror.yml` (consumer-owned, §6).

#### 3. One-operation tagging: `auto-tag-data.yml`

On `push: branches: [main], paths: [<version-source-file>]`, plus `workflow_dispatch` that **reconciles whatever the file currently claims** (not a `HEAD~1` diff — the escape hatch must be useful in exactly the case it exists for, where the bad merge is several commits back).

Four properties, each one a paid-for lesson from [exoma-ch/nucl-parquet#350](https://github.com/exoma-ch/nucl-parquet/issues/350):

- **Push the tag with a GitHub App installation token**, so `on: push: tags:` fires. `GITHUB_TOKEN` by design cannot trigger a downstream workflow, which forces the two-operation shape (push tag, then dispatch over a long-lived PAT) — and that is precisely how #344 happened: the tag push succeeded, the dispatch 401'd on an expired PAT, and the half-completed state was unrecoverable because the workflow's own "refusing to re-tag" guard blocked the retry. The devkit already has this credential pattern ([`COMMIT_APP`](https://github.com/vig-os/devkit/blob/main/docs/WORKFLOW_SECURITY.md)); reuse it.
- **Exercise every credential *before* any ref moves.** A broken credential must leave a clean retry, not a half-published version. Includes asserting the downstream workflow's `state == "active"` — a disabled `release-data.yml` is the same bug wearing a different hat.
- **Idempotent over the full `(tag_exists × release_exists)` matrix.** Both true → green no-op. Tag missing, release present → **refuse** (re-tagging would re-point a published, signed release at current `main`). Tag present, release missing → **re-trigger**, never refuse. Neither → tag. And resolve "is there a release?" from the HTTP status, not from whether the command succeeded: treating any failure as "no release" lets a transient API error re-publish an already-published version.
- **Assert the trigger, do not assume it.** Poll for the downstream run; if it never appears, the error message must carry the verbatim remedy command. #344 sat unnoticed because that remedy lived only in somebody's head.

`concurrency: cancel-in-progress: false` — cancelling a run that has already pushed the tag abandons it before the confirmation step, reintroducing the same unwatched half-state by another route.

#### 4. Integrity: a shipped composite action, not a copied script

`.github/actions/data-manifest` + `data-sign`, with the contract, not the payload, fixed:

- **Manifest**: per-file path → digest, plus release-level fields (version, tag, archive digest, file count). Two hard gates: a **floor** (refuse to sign a manifest listing implausibly few files — an empty manifest signs and publishes perfectly happily while asserting nothing), and **set equality** between the archive's members and the manifest's keys. The archive and the manifest are built by different tools over different exclusion rules; asserting that they agree — rather than trusting it — is what stops a file shipping without a manifest entry.
- **Signature**: over the archive *and* the manifest, with the version+tag+digest bound into the signed trusted comment, so the signature attests to *which release* these bytes are and a valid signature cannot be replayed onto a different one. Key material written to `RUNNER_TEMP` under `umask 077` with a `shred` trap — never into the workspace, where a release-asset glob could sweep it up. Verified against the **committed** public key before upload.
- **Signing backend is a choice, not a baked-in tool** — see the spike matrix below. Default to GitHub artifact attestations (zero ceremony, already in the ceiling); `minisign` / `cosign` opt-in for consumers that must be verifiable offline.

#### 5. `reconcile-data-release.yml` — assert the invariant, not the mechanism

Weekly (off the hour — GitHub drops scheduled runs when too many fire at `:00`) + `workflow_dispatch`. Asserts: *the version the repo claims is published, carries every expected asset, and its signature verifies against the committed public key.* On failure it **opens or updates a labelled tracking issue** (dedupe by label, never by title or body text — titles carry the version and GitHub's body search is indexed asynchronously), closes it when the invariant holds again, and goes red second. `if: always()` on the filing step is load-bearing: an implicit `success()` gate means an `apt` hiccup suppresses the one signal that reaches a person while the job still goes red — which is the exact failure the lane exists to stop.

Needs `issues: write`, which is why it uses `GITHUB_TOKEN` and not the App token — worth documenting as the general rule: *confirm the credential actually holds the permission*, rather than reaching for the App token by reflex.

#### 6. Mirror seam: `release-data-mirror.yml`

Standalone, consumer-owned, preserved on upgrade, no-op default. Two invariants the devkit *does* enforce, both from [exoma-ch/nucl-parquet#283](https://github.com/exoma-ch/nucl-parquet/issues/283):

- **Declared state, not inferred state.** A mirror is enabled by a repository **variable**; the token is a secret. Variable unset → job **skipped** (grey, and honestly so). Variable set, token missing → job **fails loudly**. Never "warn and skip when the secret is absent" — that reports success while doing nothing, and a skipped job emits no log to say so.
- **Metadata is generated from the repo's compliance record on every release**, never hand-maintained — so a published licence claim cannot drift from the licence record (#234).

Docs must also state the retirement path: to retire a mirror, drop the job *and* the consumer-facing URLs that point at it together, so nobody is left pointed at something nobody updates.

#### 7. Docs

New `docs/DATA_RELEASE.md` (SSoT), linked from `docs/RELEASE_CYCLE.md` and `docs/DOWNSTREAM_RELEASE.md`. Spike writeup under `docs/spikes/<issue>-data-release-targets/` per the [`1206-workflow-model`](https://github.com/vig-os/devkit/tree/main/docs/spikes/1206-workflow-model) convention.

---

### Spike: targets and tooling

Sizing anchor — nucl-parquet's published data assets: **617 MB** (`data-2026.7.0`, 2026-07-10) → **748 MB** (`data-2026.8.0`) → **967 MB** (`data-2026.8.5`, 2026-09-28). ~+350 MB in 2.5 months. **The 2 GiB GitHub Release asset ceiling is roughly eight months out at that rate**, so the contract must support sharding/multi-part *before* it is needed, and a second target is not speculative.

#### Distribution targets

| Tier | Target | Tooling | Size ceiling | Immutability / versioning | CI auth | Integrity | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **0 — canonical** | GitHub Releases | `gh release upload --clobber`, `softprops/action-gh-release` | **2 GiB per asset**, ≤1000 assets per release | Tag + immutable-releases setting locks tag *and* assets on publish | `GITHUB_TOKEN` / App token — already present | sha256 + detached sig + `gh attestation verify` | **Ship.** System of record. Assets must land in the **draft window** (§3, [#1746](https://github.com/vig-os/devkit/issues/1746) §2). Shard before 2 GiB. |
| **1 — mirror** | Hugging Face Hub dataset repo | `hf upload <repo> <dir> --repo-type dataset` (**note:** `hf upload-large-folder` is deprecated; `hf upload` handles large folders, streams in several commits, and resumes on re-run), or `huggingface_hub` Python | ~300 GB/repo soft limit (more on request); ≤~100k files recommended; ≤5 GB/file without special handling, chunk very large files; Xet dedup | Git revisions; no publish-time lock | `HF_TOKEN` write-scoped — **new secret**, declared-state gated | No publisher signature; **Croissant JSON-LD auto-generated** → indexed by Google Dataset Search | **Ship as the reference mirror recipe.** Buys lazy per-file HTTP fetches, a dataset viewer and discoverability. Not a system of record. |
| **1 — mirror** | OCI artifact on `ghcr.io` | `oras push ghcr.io/<org>/<repo>-data:<version> <file>:<mediatype>`, `--artifact-type`; `oras-py`; prior art uses `application/bagit-1.0` | Registry-bound, effectively unbounded; multi-layer → **sharding is native** | **Content-addressed by digest — immutability for free**; tags are mutable, digests are not | **`packages: write`, which the extension ceiling already grants — no new secret** | `cosign` signs OCI refs natively; referrers API carries attestations | **Ship — strongest technical fit.** Zero new credentials, native >2 GiB, native offline/air-gapped pull (`oras pull` into a bastion). Recommend as the default second target. |
| **2 — opt-in** | Zenodo / InvenioRDM | REST API upload (`developers.zenodo.org`); pre-reserved DOI | 50 GB per record on the new API (legacy: 100 MB/file) | Versioned records, concept DOI + per-version DOI; published records are archival | Zenodo token — **new secret** | Checksums per file; no publisher signature | **Ship as an opt-in recipe** for citable research data (`exoma-ch/nucl-parquet`, `vig-os/tessera`). **Caveat worth documenting loudly:** the built-in GitHub-release integration archives the *source tree*, not the release assets ([zenodo/zenodo#1235](https://github.com/zenodo/zenodo/issues/1235)) — a data release needs an explicit API upload step, not the checkbox. |
| **3 — escape hatch** | S3 / R2 / B2 + `rclone` | `rclone sync`, `aws s3 cp` | Unbounded | Only with object-lock / versioning | Cloud creds — **new secret + a bill** | Whatever you build | **Seam only, no shipped recipe.** For >50 GB. R2's zero-egress is the pragmatic pick, but it adds a credential, a bill and zero discoverability. |
| **rejected** | `git-lfs` in-repo | `git lfs track` | 2 GiB/file; GitHub moved to **metered billing** (data packs discontinued): 10 GB storage+bandwidth free on Free/Pro, 250 GB on Team/Enterprise | Every historical version stays in storage **forever** | Native | Git object integrity | **Reject** for a ~1 GB/refresh cadence. Bandwidth is metered **per clone**, so cost scales with consumer popularity and is unbounded by the publisher. Fine only for small (<100 MB), slowly-changing fixtures. |
| **out of scope** | DVC / lakeFS / Dolt | — | — | — | — | — | **Non-goal.** These change the repo's *working* model, not its release step. The lane releases artefacts; it does not version working data. Likewise `vig-os/nvd-mirror`'s shape (a continuously committed mirror with no versioned release) is a different problem. |

#### Integrity and metadata tooling

**Manifest format** — three real options, to be decided in the spike rather than pre-committed here:

| Option | For | Against |
| --- | --- | --- |
| Bespoke `manifest.json` (nucl-parquet today) | Exactly the fields the lane needs; trivial to generate and verify | One more private format for consumers to learn; no tooling ecosystem |
| **BagIt — [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html)** | IETF standard; payload manifest of per-file checksums is *precisely* this use case; in-place upgrade to stronger hash algorithms without breaking compatibility; digital-preservation tooling exists; ORAS dataset prior art already uses `application/bagit-1.0` | It is a *directory layout*, so the serialized-bag-in-a-tarball shape needs a written convention |
| Frictionless `datapackage.json` | Good schema story for tabular resources | Oriented at tabular schemas, not arbitrary binary payloads or fixity; poor fit |

Leaning **BagIt for the on-the-wire package** plus a small release-level JSON sidecar for the fields the train itself reads (version, tag, archive digest) — standards-aligned without contorting the manifest into carrying release metadata.

**Signature backend:**

| Option | For | Against | Recommendation |
| --- | --- | --- | --- |
| **GitHub artifact attestations** (`actions/attest-build-provenance`, `subject-digest: sha256:…`, verify with `gh attestation verify`) | Zero key ceremony; `attestations: write` + `id-token: write` are **already in the extension ceiling**; SLSA provenance in in-toto format, Sigstore-signed | GitHub-bound; asserts *provenance* ("this workflow built these bytes"), not *publisher endorsement*; offline verification is awkward | **Default.** Free, already permitted, no rotation runbook. |
| `cosign sign-blob --bundle` (keyless OIDC) | No long-lived key; transparency log; bundle carries cert + timestamp + inclusion proof | Verification needs an identity/issuer policy the consumer must get right; still online-ish | **Opt-in**, natural pairing with the OCI target since `cosign` signs OCI refs natively. |
| `minisign` (offline keypair, committed public key) | Tiny; **verifiable fully offline with one pinned public key** — the air-gapped case; the trusted comment is covered by the signature, so version+tag+digest can be bound into it | A key to hold, a password secret, and a rotation runbook the consumer must write | **Opt-in, and the right default for air-gapped consumers.** This is what nucl-parquet needs and why. |

**Discoverability metadata:** **Croissant** (MLCommons, JSON-LD over schema.org, four metadata layers) — HF's dataset viewer auto-generates it for every Hub dataset and Google Dataset Search indexes it. Ship as an optional generated sidecar on the GitHub-Releases target so the canonical release is discoverable even when the HF mirror is off.

### Alternatives Considered

- **(A) Parameterise the existing train to accept a second version format and tag prefix.** Rejected. The train's unit of work is a changelog-frozen release branch with a human-approved PR and a single promote gate; a data refresh has none of that. Coupling them means a data fix waits on a code release train — and the `concurrency: group: release` lock means the two would serialise against each other for no reason.
- **(B) Fold data publishing into [#1746](https://github.com/vig-os/devkit/issues/1746)'s `publish-release-extension.yml`.** Rejected. That seam fires on `release: published` of a **code** release. A data refresh is not a code release and must not require one. The two issues should share §2 (the draft asset window) and nothing else.
- **(C) Ship an opinionated data-release *tool*** (tarball layout + HF sync + DOI minting baked in). Rejected on smallest-denominator grounds ([#1519](https://github.com/vig-os/devkit/issues/1519)). The archive layout, catalog shape, shard naming and licence records are irreducibly per-project. The devkit ships the state machine, the integrity gates and the seam.
- **(D) Leave it to each repo.** Rejected — this is the "third adopter rediscovers it" cut. nucl-parquet needed six issues to get the state machine right ([#289](https://github.com/exoma-ch/nucl-parquet/issues/289), [#296](https://github.com/exoma-ch/nucl-parquet/issues/296), [#283](https://github.com/exoma-ch/nucl-parquet/pull/283), [#344](https://github.com/exoma-ch/nucl-parquet/issues/344), [#350](https://github.com/exoma-ch/nucl-parquet/pull/350), [#364](https://github.com/exoma-ch/nucl-parquet/issues/364)) — two of them production incidents where a published version was undownloadable. Candidate next adopters in the orgs: `exoma-ch/talys` (Parquet output), `exoma-ch/theranostics-landscape`, `vig-os/tessera` (FAIR data products — the DOI/Croissant row is squarely for it).
- **(E) Use `git-lfs` and skip the whole lane.** Rejected on economics — see the spike table. Metered per-clone bandwidth makes the publisher's cost a function of consumer popularity, and LFS storage is append-only across history.

### Acceptance Criteria

- [ ] `DEVKIT_DATA_RELEASE=true` in `.vig-os` scaffolds the data lane; `false`/absent scaffolds nothing and every existing consumer is byte-identical.
- [ ] `DEVKIT_DATA_VERSION_SOURCE=<path>#<json-pointer>` and `DEVKIT_DATA_VERSION_FORMAT` are validated at scaffold time; invalid values fail with a message naming the accepted set.
- [ ] Data tags use `DEVKIT_DATA_TAG_PREFIX` and are provably independent of `DEVKIT_TAG_PREFIX`: a data release and a code release can run concurrently without sharing a concurrency group, a tag namespace, or the changelog.
- [ ] A merge to `main` that changes the version-source file produces the matching tag in **one operation** (App-token push firing `on: push: tags:`), and no path exists that pushes a tag without the release workflow starting.
- [ ] `auto-tag-data.yml` verifies every credential *and* the downstream workflow's `active` state **before** any ref moves; a missing credential leaves the repo untouched.
- [ ] `auto-tag-data.yml` is idempotent across all four `(tag_exists × release_exists)` states, with the documented action for each, and "is there a release?" is resolved from HTTP 404 specifically — not from command failure.
- [ ] `auto-tag-data.yml` confirms the release workflow started and, on timeout, emits the verbatim recovery command.
- [ ] `release-data.yml` **blocks packaging and signing on the consumer's CI suite passing** — a test proves no asset can be published while `verify` is incomplete.
- [ ] The tag's version and the version-source file's value are asserted equal before any asset is built.
- [ ] Assets land in the **draft** Release before publish, so the lane is correct under immutable releases; a test covers the ≥1 GiB retry path.
- [ ] The manifest gate refuses (a) a manifest below a configured file-count floor and (b) any disagreement between archive members and manifest keys, with the diff printed both ways.
- [ ] Signing hard-fails when the configured backend's credentials are absent — an unsigned data release is impossible, not merely unusual — and verifies against the committed public key before upload.
- [ ] `reconcile-data-release.yml` opens **and** updates **and** closes a single label-deduped tracking issue, files it under `if: always()` even when an earlier step failed, and goes red second.
- [ ] `release-data-mirror.yml` ships as a preserved no-op seed; the declared-state gate is tested for all three states (unset → skipped, set without token → **failed**, set with token → runs).
- [ ] `docs/DATA_RELEASE.md` exists as SSoT, linked from `RELEASE_CYCLE.md` and `DOWNSTREAM_RELEASE.md`, and carries: the target matrix with its verdicts, the HF + OCI + Zenodo recipes, the signing-backend decision table, the mirror retirement path, and the Zenodo "archives the source tree, not your assets" caveat.
- [ ] `docs/spikes/<issue>-data-release-targets/` records the target/tooling evaluation and the manifest-format decision.
- [ ] `exoma-ch/nucl-parquet` can adopt the devkit and retire all three of its hand-written data workflows, keeping its CalVer namespace, its minisign key, its manifest gate and its HF mirror — with no bespoke workarounds. **This is the acceptance test for the whole cut.**
- [ ] No existing consumer (`h5v`, `scitadel`, `devkit` itself) changes behaviour.

### Additional Context

**Prior art, file by file** — [exoma-ch/nucl-parquet](https://github.com/exoma-ch/nucl-parquet). These workflows are unusually well-commented; every guard names the incident that produced it, and that commentary is the real specification for this issue:

- [`release-data.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/release-data.yml) — CI-gated packaging, tag↔catalog assertion, content manifest with the members≡keys gate, unconditional minisign of archive **and** manifest with version/tag/digest bound into the trusted comment, verification against the committed public key, then upload. Plus the HF mirror job and its declared-state gate.
- [`auto-tag-data.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/auto-tag-data.yml) — the one-operation tag state machine, credential preflight, the four-state matrix, and the "confirm the downstream run started" poll.
- [`reconcile-data-release.yml`](https://github.com/exoma-ch/nucl-parquet/blob/main/.github/workflows/reconcile-data-release.yml) — the weekly invariant assertion and the issue-as-signal pattern.
- Supporting consumer-side surface worth studying: `scripts/verify_data_release.sh`, `scripts/reconcile_data_release.sh`, `scripts/gen_signing_key.sh`, `scripts/sync_huggingface.py`, `docs/security/data-signing.md`, `docs/security/data-signing-key.pub`, and the published release-scheme table in its README (data on CalVer, code on semver).
- Observable state today: `data-2026.8.5` = `nucl-parquet-data-2026.8.5.tar.zst` (967 MB) + `.minisig` + `.manifest.json` + `.manifest.json.minisig`. Note the retrofit boundary — `data-2026.8.1` and earlier carry no signature, `data-2026.8.2` no manifest. A shipped lane means later adopters start at the current bar instead of walking that same path.

**Devkit contract this plugs into:**

- Orchestrator: [`assets/workspace/.github/workflows/release.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release.yml)
- Version gate / RC computation: [`release-core.yml#L176`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L176), [`#L224-L282`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-core.yml#L224-L282)
- Release-object ownership: [`release-publish.yml#L177`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-publish.yml#L177) (tag ref), [`#L269`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-publish.yml#L269) (`gh release create --verify-tag --draft`)
- Existing seams: [`release-extension.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/release-extension.yml) (read-only, pre-tag), [`prepare-release-extension.yml`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/workflows/prepare-release-extension.yml) (mutating, release branch) — and devkit's own dogfooding of the latter in [`.github/workflows/prepare-release-extension.yml`](https://github.com/vig-os/devkit/blob/main/.github/workflows/prepare-release-extension.yml)
- Tag prefix resolution: [`resolve-toolchain/action.yml#L169`](https://github.com/vig-os/devkit/blob/main/assets/workspace/.github/actions/resolve-toolchain/action.yml#L169)
- Feature gating precedent: [`assets/init-workspace.sh#L531`](https://github.com/vig-os/devkit/blob/main/assets/init-workspace.sh#L531) (`DEVKIT_FEATURES_DISABLED`), `#L798` (`DEVKIT_LANGUAGES` — the sticky declared-list pattern)
- Docs: [`DOWNSTREAM_RELEASE.md`](https://github.com/vig-os/devkit/blob/main/docs/DOWNSTREAM_RELEASE.md) (§ Extension Hook, § Permission ceiling, § Immutable releases), [`RELEASE_CYCLE.md`](https://github.com/vig-os/devkit/blob/main/docs/RELEASE_CYCLE.md), [`WORKFLOW_SECURITY.md`](https://github.com/vig-os/devkit/blob/main/docs/WORKFLOW_SECURITY.md)

**External references (verified 2026-09-28):**

- GitHub: [about releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) (2 GiB per asset, ≤1000 assets), [preventing changes to your releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/preventing-changes-to-your-releases), [Git LFS billing](https://docs.github.com/billing/managing-billing-for-git-large-file-storage/about-billing-for-git-large-file-storage) + [metered-billing FAQ](https://github.com/orgs/community/discussions/61362), [artifact attestations](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds), [`actions/attest-build-provenance`](https://github.com/actions/attest-build-provenance)
- Hugging Face: [repository limitations and recommendations](https://huggingface.co/docs/hub/en/repositories-recommendations), [storage limits](https://huggingface.co/docs/hub/en/storage-limits), [CLI guide](https://huggingface.co/docs/huggingface_hub/main/en/guides/cli) (`hf upload`; `upload-large-folder` deprecated), [dataset upload decision guide](https://huggingface.co/docs/hub/en/datasets-upload-guide-llm), [Croissant metadata](https://huggingface.co/docs/dataset-viewer/en/croissant)
- ORAS: [oras.land docs](https://oras.land/docs/), [pushing and pulling](https://oras.land/docs/how_to_guides/pushing_and_pulling/), [compatible registries](https://oras.land/docs/compatible_oci_registries/), [`oras-py`](https://oras-project.github.io/oras-py/), dataset prior art: [mbjones/oci-datasets](https://github.com/mbjones/oci-datasets)
- Zenodo: [developers.zenodo.org](https://developers.zenodo.org/), [GitHub integration docs](https://rue-a.github.io/github-zenodo-integration/documentation/), [pre-reserving a DOI](https://support.zenodo.org/help/en-gb/24-github-integration/73-can-i-pre-reserved-a-doi-before-a-github-release), [release-assets caveat (zenodo#1235)](https://github.com/zenodo/zenodo/issues/1235), [InvenioRDM roadmap](https://inveniosoftware.org/products/rdm/roadmap/)
- Standards: [BagIt RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html), [Croissant (MLCommons)](https://mlcommons.org/working-groups/data/croissant/), [Frictionless Data Package](https://packages.oit.ncsu.edu/cran/web/packages/frictionless/vignettes/frictionless.html)
- Signing: [`cosign sign-blob`](https://github.com/sigstore/cosign/blob/main/doc/cosign_sign-blob.md), [Chainguard: signing blobs with cosign](https://edu.chainguard.dev/open-source/sigstore/cosign/how-to-sign-blobs-with-cosign/), [minisign](https://jedisct1.github.io/minisign/)

### Impact

- **Beneficiaries:** any devkit consumer that publishes a dataset alongside (or instead of) code. Immediate: `exoma-ch/nucl-parquet` (blocked from adopting today — its data lane is the reason), `vig-os/tessera` (FAIR data products; the DOI + Croissant rows exist for it), `exoma-ch/talys` and `exoma-ch/theranostics-landscape` (Parquet outputs, no release lane yet).
- **Compatibility:** purely additive. The lane is opt-in via `DEVKIT_DATA_RELEASE`, defaults off, and scaffolds nothing when off. No change to the code train's version model, tag namespace, concurrency group or promote gate. Every existing consumer is byte-identical.
- **Coupling to [#1746](https://github.com/vig-os/devkit/issues/1746):** this issue depends on #1746's §2 (draft-Release-first + the named pre-publish assets window) and should land after it, or share that section. It does **not** depend on #1746's §1 (pre-release format) or §3 (`publish-release-extension.yml`).
- **Sequencing suggestion:** cut §§1–4 (keys, lane, one-operation tagging, integrity) as the MVP; §§5–6 (reconciliation, mirror recipes) as a fast follow-up; the Zenodo/DOI recipe last, since it is the only target with no adopter blocked on it today.

### Changelog Category

Added

