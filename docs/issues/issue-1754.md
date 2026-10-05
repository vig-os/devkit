---
type: issue
state: open
created: 2026-09-28T21:17:18Z
updated: 2026-09-29T15:32:20Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1754
comments: 3
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:49.215Z
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
| `DEVKIT_DATA_PACKAGE_FORMAT` | `archive+manifest` | Wire package provider (§4). `bagit`, `oci-native`, `frictionless`, or `custom` for a self-sealing consumer format. |
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
7. **`landed`** — run each enabled target's landing probe with the authority a consumer would have (§7). A target that published but did not land fails the lane and says which one.

#### 3. One-operation tagging: `auto-tag-data.yml`

On `push: branches: [main], paths: [<version-source-file>]`, plus `workflow_dispatch` that **reconciles whatever the file currently claims** (not a `HEAD~1` diff — the escape hatch must be useful in exactly the case it exists for, where the bad merge is several commits back).

Four properties, each one a paid-for lesson from [exoma-ch/nucl-parquet#350](https://github.com/exoma-ch/nucl-parquet/issues/350):

- **Push the tag with a GitHub App installation token**, so `on: push: tags:` fires. `GITHUB_TOKEN` by design cannot trigger a downstream workflow, which forces the two-operation shape (push tag, then dispatch over a long-lived PAT) — and that is precisely how #344 happened: the tag push succeeded, the dispatch 401'd on an expired PAT, and the half-completed state was unrecoverable because the workflow's own "refusing to re-tag" guard blocked the retry. The devkit already has this credential pattern ([`COMMIT_APP`](https://github.com/vig-os/devkit/blob/main/docs/WORKFLOW_SECURITY.md)); reuse it.
- **Exercise every credential *before* any ref moves.** A broken credential must leave a clean retry, not a half-published version. Includes asserting the downstream workflow's `state == "active"` — a disabled `release-data.yml` is the same bug wearing a different hat.
- **Idempotent over the full `(tag_exists × release_exists)` matrix.** Both true → green no-op. Tag missing, release present → **refuse** (re-tagging would re-point a published, signed release at current `main`). Tag present, release missing → **re-trigger**, never refuse. Neither → tag. And resolve "is there a release?" from the HTTP status, not from whether the command succeeded: treating any failure as "no release" lets a transient API error re-publish an already-published version.
- **Assert the trigger, do not assume it.** Poll for the downstream run; if it never appears, the error message must carry the verbatim remedy command. #344 sat unnoticed because that remedy lived only in somebody's head.

`concurrency: cancel-in-progress: false` — cancelling a run that has already pushed the tag abandons it before the confirmation step, reintroducing the same unwatched half-state by another route.

#### 4. Integrity: a **pluggable wire package**, plus a shipped composite action

The devkit fixes the *contract*, never the package format. A **wire package provider** is declared by `DEVKIT_DATA_PACKAGE_FORMAT` and supplies four operations the lane calls:

| Op | In | Out | Why the lane needs it |
| --- | --- | --- | --- |
| `pack` | payload + version | artefact file(s) | build the thing that ships |
| `members` | artefact | `path → digest` map | feeds the set-equality gate and lets a *partial* transfer be verified |
| `root-digest` | artefact | one digest that transitively commits to every member | what gets signed, attested and pinned |
| `verify` | artefact (+ trust material) | exit 0/1 | what a **consumer** runs, offline |

Each provider also declares what it already does, so the lane skips what it must not duplicate:

```
provides: members, root_digest, offline_verify, signature
```

Two rules follow, and they are the whole point of the abstraction:

- **The lane signs the root digest; it never re-derives integrity a format already provides.** Wrapping a self-sealing container in a second, weaker manifest is a downgrade dressed as diligence.
- **If a format supplies `signature`, the lane verifies it and stops.** It does not add a second signature under a different key — "which signature is authoritative?" must never be a live question at the point of consumption.

Where the lane *does* build the manifest (the `provides` set is missing `members`), two hard gates apply: a **file-count floor** (an empty manifest signs and publishes perfectly happily while asserting nothing) and **set equality** between the archive's members and the manifest's keys, printed both ways on failure. Archive and manifest are built by different tools over different exclusion rules; asserting that they agree — rather than trusting it — is what stops a file shipping without a manifest entry.

Signing, where the lane does it: key material to `RUNNER_TEMP` under `umask 077` with a `shred` trap, never into the workspace where a release-asset glob could sweep it up; version+tag+digest bound into the signed comment so a signature cannot be replayed onto a different release; verified against the **committed** public key before upload.

#### 5. `reconcile-data-release.yml` — assert the invariant, not the mechanism

Weekly (off the hour — GitHub drops scheduled runs when too many fire at `:00`) + `workflow_dispatch`. Asserts: *the version the repo claims is published, carries every expected asset, and its signature verifies against the committed public key.* On failure it **opens or updates a labelled tracking issue** (dedupe by label, never by title or body text — titles carry the version and GitHub's body search is indexed asynchronously), closes it when the invariant holds again, and goes red second. `if: always()` on the filing step is load-bearing: an implicit `success()` gate means an `apt` hiccup suppresses the one signal that reaches a person while the job still goes red — which is the exact failure the lane exists to stop.

Needs `issues: write`, which is why it uses `GITHUB_TOKEN` and not the App token — worth documenting as the general rule: *confirm the credential actually holds the permission*, rather than reaching for the App token by reflex.

#### 6. Mirror seam: `release-data-mirror.yml`

Standalone, consumer-owned, preserved on upgrade, no-op default. Two invariants the devkit *does* enforce, both from [exoma-ch/nucl-parquet#283](https://github.com/exoma-ch/nucl-parquet/issues/283):

- **Declared state, not inferred state.** A mirror is enabled by a repository **variable**; the token is a secret. Variable unset → job **skipped** (grey, and honestly so). Variable set, token missing → job **fails loudly**. Never "warn and skip when the secret is absent" — that reports success while doing nothing, and a skipped job emits no log to say so.
- **Metadata is generated from the repo's compliance record on every release**, never hand-maintained — so a published licence claim cannot drift from the licence record (#234).

Docs must also state the retirement path: to retire a mirror, drop the job *and* the consumer-facing URLs that point at it together, so nobody is left pointed at something nobody updates.

#### 7. Landing verification: did the release actually arrive, at every target?

Publishing is not landing. A mirror push can return 200 and leave the target serving the previous version; an asset can upload and be unreadable; a DOI can mint against the wrong files. So each enabled target declares a **landing probe** the lane runs *after* publish, and the reconcile lane (§5) re-runs on schedule.

This is not new machinery — it is [`docs/CROSS_REPO_RELEASE_GATE.md`](https://github.com/vig-os/devkit/blob/main/docs/CROSS_REPO_RELEASE_GATE.md) applied to a second artefact class. That contract already exists to *"validate release artifacts **outside the release repository execution context**"* and to *"keep release orchestration and validation responsibilities separated"*, over a `repository_dispatch` payload. The data lane reuses it — `client_payload[tag]` plus the target set — rather than inventing a parallel one.

**The probe runs with the least authority a real consumer would have — and for a public target that means none.**

This is the part worth arguing for explicitly, because the instinct is the opposite. Verifying a public artefact with a privileged token exercises a code path **no consumer will ever take**: it can succeed against an object the public cannot read, against a repo whose visibility flipped, against a registry whose anonymous-pull policy changed. The probe's whole job is to answer *"can a consumer get this?"*, so it must ask the question the way a consumer asks it.

| Target | Probe | Credential |
| --- | --- | --- |
| GitHub Release | asset set complete, sizes non-zero, `root-digest` matches the signed comment, **signature verifies against the committed public key** | none — unauthenticated `https://github.com/.../releases/download/...` on a public repo; `contents: read` only if private |
| HF dataset | revision resolves, `root-digest` matches, generated card's licence block equals the repo's licence record | none if public; read-scoped `HF_TOKEN` if gated |
| OCI / ghcr | `oras manifest fetch` by **tag**, digest equals the published `root-digest` | none if public; read token if private |
| Zenodo/DOI | DOI resolves, record files' checksums match | none — published records are public |

So the answer to *"does each target need a GitHub App?"* is **mostly no, and deliberately so**:

- **Write paths already have one, and should not get another.** Devkit already mandates two ([DOWNSTREAM_RELEASE.md § Required App Secrets](https://github.com/vig-os/devkit/blob/main/docs/DOWNSTREAM_RELEASE.md#required-app-secrets)): `COMMIT_APP_*` for protected-ref writes, `RELEASE_APP_*` for release orchestration — with `github.token` explicitly not a fallback. The data lane's tag push (§3) **reuses the Commit App**; it does not mint a third. nucl-parquet reached the same conclusion independently in [#350](https://github.com/exoma-ch/nucl-parquet/pull/350) (reuse the existing release App rather than keep a bespoke PAT alive — the PAT expiring is what caused [#344](https://github.com/exoma-ch/nucl-parquet/issues/344)).
- **Read/verify paths should have less authority, not more.** A new read-scoped App per target is a credential to rotate, an installation to keep current, and a way for the probe to pass while consumers are locked out.
- **The one place an App is genuinely right** is an *independent observer*: a reconcile job that must `issues: write` to file the tracking signal, or that watches from a different repository (the cross-repo gate shape). And even there, check the scope rather than reaching by reflex — nucl-parquet's App installation carries `{contents, metadata, pull_requests}` and **no `issues` scope**, so its reconcile lane deliberately runs on `GITHUB_TOKEN`. The rule to write into the docs is **"confirm the credential actually holds the permission you need"**, not "use the App token".

Running post-publish tests (not just presence probes) against the landed artefact is the same seam: the probe target may be a consumer repo's own CI, dispatched exactly as the cross-repo gate already dispatches, which is how you get "the clients still work against the bytes we just shipped" rather than "the bytes exist".

#### 8. Confirmation at scale — what changes when the artefact is big

Three failure modes appear at size that simply do not exist for a 5 MB asset:

1. **A partial upload that reports success.** The API call returns 200, the asset row exists, the bytes are truncated.
2. **Confirmation itself becomes expensive.** "Download it and hash it" × N targets × every release is minutes of CI and gigabytes of egress per release. **Confirmation must be O(1) in artefact size**, or it will be quietly disabled the first time it makes a release slow.
3. **Past the per-asset ceiling you ship a *set*** — and a set of individually valid parts can still be the *wrong* set.

**Every target already computes a digest server-side. Read it; do not re-download.**

| Target | Server-side confirmation | Cost |
| --- | --- | --- |
| GitHub Releases | `.assets[].state == "uploaded"` **and** `.assets[].digest == "sha256:<hex>"` — computed by GitHub at upload, immutable, [GA 2025-06-03](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/). `null` on pre-GA assets, so treat null as "unknown", never as "fine" | 1 API call |
| HF dataset | `repo_info(..., files_metadata=True)` → per-file size + LFS `sha256`; the Xet CAS verifies xorb integrity on ingest. **Only valid for a handful of files** — at file-count scale this does not hold; see "Two regimes" below | 1 API call (few-large only) |
| OCI / ghcr | **Intrinsic — the registry rejects a blob whose content does not match its digest.** A successful push *is* the confirmation; `oras manifest fetch --descriptor <repo>:<tag>` resolves tag → manifest digest to confirm what the tag now points at | 1 API call |
| Zenodo | record files' `checksum` (`md5:<hex>`; Zenodo stores two independent MD5s, one to detect out-of-band modification) | 1 API call |

**The confirmation is a three-way agreement, and it is free:**

```
digest bound into the signature  ==  digest the target computed  ==  digest computed at pack time
```

Verified live against `data-2026.8.5` while writing this section:

- minisign trusted comment (covered by the signature): `sha256=938d46e4cef3fa9ec98eb3c4d2a42b5bf36054cd654f843997dc2f81e634647d`
- GitHub REST `.assets[].digest`: `sha256:938d46e4cef3fa9ec98eb3c4d2a42b5bf36054cd654f843997dc2f81e634647d`
- `.assets[].state`: `uploaded`, `.assets[].size`: `1014354062`

**967 MiB artefact; the whole confirmation cost one API call and a 378-byte signature fetch.** Note which direction the strength runs: GitHub's digest is a **third-party computation over the bytes the target actually holds**. Agreeing with the signed digest says *the bytes the target is serving are the bytes we signed* — strictly stronger than "our hash of our own file matched", which is what a naive re-download-and-hash probe actually tests.

This is also why §4's rule matters: bind the digest **into the signature** (trusted comment or equivalent), not merely alongside it. A digest in a sidecar file confirms nothing against an attacker who can replace the artefact, because they can replace the sidecar too.

**Cheap evidence about the *served* bytes.** The digest describes the stored object; consumers get a CDN in front of it. Range requests work on release downloads — verified: `accept-ranges: bytes`, `HTTP 206`, `content-range: bytes 0-63/1014354062`, served from Azure Blob — so a probe can confirm, for kilobytes: total size (from `content-range`), format magic (`28 b5 2f fd` = zstd), and a random middle chunk against the per-file manifest. **This is the second place the per-file manifest earns its keep** ([exoma-ch/nucl-parquet#296](https://github.com/exoma-ch/nucl-parquet/issues/296)) — partial verification is only meaningful if you have per-file digests to check it against.

**Sharding: confirmation becomes a set property.** Past the 2 GiB per-asset ceiling the artefact ships as parts, and "every part is valid" is no longer sufficient:

- every part present, each with `state: uploaded`,
- every part's digest matching its manifest entry,
- **and a `root-digest` over the ordered set** — a Merkle root, or a digest of the ordered list of part digests.

Without the third, a complete set of individually valid parts drawn from *two different releases* confirms perfectly and reassembles into garbage. That is precisely what §4's `root-digest` op exists for, and why a provider that already has one (tessera's MMR `content_hash`) needs nothing added.

##### Two regimes, and they invert several answers

Everything above assumes the **few-large** regime (nucl-parquet: four assets, one of them 967 MiB). The **many-small** regime — [morepet/mat-vis](https://github.com/morepet/mat-vis), ~3000 PBR materials × channels × tiers ≈ **28k LFS files** per release — inverts the target choice, the atomicity story, and the confirmation mechanism. The lane must know which regime it is in, because advice correct in one is wrong in the other.

| | **Few-large** (nucl-parquet) | **Many-small** (mat-vis) |
| --- | --- | --- |
| Shape | 4 assets, 967 MiB tarball | ~28k files, KB–MB each |
| Canonical target | **GitHub Releases** | **HF Datasets** — GH Releases is *wrong* here |
| Why | 2 GiB/asset ceiling is the only constraint | GH Releases has **no atomic multi-file commit** |
| Binding constraint | asset size | per-directory count, commit rate, tree pagination |
| Confirmation | O(1) digest read | **O(commits), not O(files)** — see below |
| Atomicity unit | one asset | one commit (a *batch*, not the release) |

**GitHub Releases is disqualified for many-small on atomicity, not size.** mat-vis's [ADR-0007](https://github.com/morepet/mat-vis/blob/main/docs/decisions/0007-substrate-move-to-hf-datasets-and-tar-container.md) attributes two bug classes directly to the substrate: dangling rowmap → missing parquet (#79, non-atomic multi-file upload) and index files written at **15 of 1965 entries** (#99, clobber-rather-than-merge across batches). A release made of N independently uploaded objects has N chances to be half-published, and the digest-per-asset confirmation from §8 does not catch a *missing* asset nobody listed.

**HF's real limits are not the documented ones.** mat-vis probed them ([`scripts/probe-hf-per-file-limits.py`](https://github.com/morepet/mat-vis/blob/main/scripts/probe-hf-per-file-limits.py), 2026-04-21):

| Files in one commit | Wall-clock | Outcome |
| ---: | :--- | :--- |
| 100 | 3.8 s | ✅ |
| 1,000 | 9.7 s | ✅ |
| 5,000 | 38 s | ✅ |
| 10,000 | 88 s | ✅ |
| 25,000 | 193 s | ❌ `too many files per directory` |

The docs say 25,000 LFS files / 1 GB per commit and suggest 50–100 files per commit to stay inside the 60 s HTTP timeout. **The limit that actually binds is 10,000 files per _directory_** — a different axis from the one documented, findable only by probing. Two further hard ceilings, both measured in production:

- **Commits: 128 per hour, per repo.** A matrix of 3 parallel sources × ~20 batch-commits each saturates it inside one rolling hour and dies on `429 … exceeded the rate limit for repository commits (128 per hour)` ([mat-vis#225](https://github.com/morepet/mat-vis/issues/225)). It is a **global per-repo counter**, so per-job `concurrency` groups do not protect it — parallel writers each see headroom and collectively blow the cap.
- **API requests: 1000 per 300 s** rolling.

**Confirmation must not enumerate files.** My §8 HF row ("one `repo_info(files_metadata=True)` call") is **wrong in this regime** and I am correcting it. HF's tree API caps at **1000 entries per page**, and with `recursive=true` *directories count as entries* — so at 3000 materials the first page came back as 1000 directories and **zero files**. mat-vis's Python client filtered for `type == file`, got an empty list, and correctly concluded `sources: {}` against a production release that was entirely fine ([mat-vis#238](https://github.com/morepet/mat-vis/issues/238)). The smoke tag (~750 entries) fit under the cap, so the bug was invisible until production scale.

So for many-small, confirmation is **not** a per-file digest sweep. It is:

1. **A committed manifest read directly** (`release-manifest.json` at a pinned revision) — never reconstructed from a tree listing. The three clients that read the manifest passed; only the one that rebuilt from the tree broke.
2. **Sentinel objects** per unit of work (mat-vis uses `<source>/<tier>/.tier_complete`) — a commit that landed says so explicitly.
3. **Expected-count assertions**, because the failure mode here is *silent incompleteness*: catalog entry count == materials baked, asserted against the upstream count. "The file exists" is not the question; "are all 1965 of them listed" is.
4. **An orphan audit.** A crash mid-batch leaves **orphaned LFS blobs with no documented auto-GC on dataset repos** ([mat-vis#190](https://github.com/morepet/mat-vis/issues/190), [#221](https://github.com/morepet/mat-vis/issues/221)), so the lane needs a housekeeping op, and the reconcile lane should report `orphans / total_lfs`.

**Container vs per-file is a real fork, and the answer is empirical.** mat-vis chose a tar container in [ADR-0007](https://github.com/morepet/mat-vis/blob/main/docs/decisions/0007-substrate-move-to-hf-datasets-and-tar-container.md) on 2026-04-19 and **reversed it two days later** in [ADR-0012](https://github.com/morepet/mat-vis/blob/main/docs/decisions/0012-per-file-substrate-drop-tar.md), because a staging bake built a ~70 GB tar that filled a 126 GB disk and wedged mid-write with no durable state. Three things the reversal establishes, which generalise:

- **Peak local disk is O(container), not O(payload).** Per-file batching peaks at O(batch) — the same source went from 70 GB to under 1 GB.
- **Batch commits are durable checkpoints.** A crash at material 1500/1993 keeps 1450 committed and a tree-listing preflight resumes at 1451. A single container has no partial state — it is resumable by construction or not at all.
- **A container defeats Xet's deduplication.** Xet's chunk-level CDC dedupes identical channel bytes *across tiers* automatically: the same `color.png` at 128/256/512/1k costs one xorb. Wrapped in per-tier tars it costs four copies. **On HF specifically, containerising is a storage pessimisation** — which is the exact opposite of the intuition that fewer, larger files are kinder to a hub.

This is the strongest argument in the whole spike for §4's provider seam being a *choice with a probe attached* rather than a default: two defensible container decisions, two days apart, same project, reversed by measurement. The lane must ship `just data-release-probe-target` — a throwaway-branch probe of per-commit latency, directory/file ceilings and commit-rate headroom — and the docs must say to run it **before** committing to a layout, not after.

**Upload-side mechanics that only bite at size:**

- `hf upload` streams in several commits and **resumes** — re-running skips already-uploaded files.
- OCI blob upload is **chunked and resumable** per the distribution spec.
- **GitHub release asset upload does not resume.** A failed 967 MiB upload restarts from zero. That is a second, independent argument for the draft window (§3 — retry into the draft rather than against a frozen release) and for sizing the job timeout for *N* attempts rather than one.
- Probes carry their own timeout and retry budget, separate from the upload's, so a slow upload cannot silently consume the confirmation step's runway.

#### 9. Setup: the credentials and the preflight are part of adoption, not of the first release

Everything above is declared config plus credentials, so it belongs in `install.sh` / `init-workspace.sh`, not in a runbook someone reads after the first failure.

- **Scaffold-time refusal, not a warning.** `DEVKIT_DATA_RELEASE=true` with a target declared and its credential absent **fails setup**. Same declared-state rule as the mirror gate (§6), one layer earlier. "Warn and continue" is how [#283](https://github.com/exoma-ch/nucl-parquet/pull/283) shipped two green releases that pushed nothing.
- **Provisioning is scripted.** Devkit already has the [`gh-app-provision`](https://github.com/vig-os/devkit/tree/main/.claude/skills/gh-app-provision) skill for App creation → `gh secret set` (PEM piped, never logged). Setup extends it to the lane: create/confirm the Commit App installation covers this repo, then set each enabled target's variable + secret pair.
- **`just data-release-preflight`** — one command that, for every *enabled* target, proves (a) the write credential works, (b) the **probe path works with the authority the probe will actually use**, and (c) the downstream workflow is `active`. Runnable locally at adoption time and run again as the lane's first job, **before any ref moves** — the ordering that turns "a human works out what happened" into "re-run the job" ([#350](https://github.com/exoma-ch/nucl-parquet/pull/350)).
- **The signing key ceremony is setup, not release.** Whichever backend a consumer picks, key generation, the committed public key, and the rotation runbook are adoption-time artefacts with a scaffolded doc stub — because the first release is the worst possible moment to discover that the committed public key and the secret have diverged.

#### 10. Docs


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

**Wire package format** — pluggable, five providers, of which the devkit ships the first two:

| Provider | `provides` | For | Against | Status |
| --- | --- | --- | --- | --- |
| **`archive+manifest`** (nucl-parquet's shape) | — | Trivial to generate and verify; exactly the fields the lane needs | One more private format; no tooling ecosystem | **Ship — default.** The zero-assumption fallback. |
| **`bagit`** — [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html) | `members` | IETF standard; payload manifest of per-file checksums is *precisely* this use case; in-place upgrade to stronger hash algorithms without breaking compatibility; digital-preservation tooling; ORAS dataset prior art already uses `application/bagit-1.0` | It is a *directory layout*, so serialized-bag-in-a-tarball needs a written convention | **Ship — recommended** for archival/air-gapped payloads. |
| **`self-sealing`** (consumer-provided) | `members`, `root_digest`, `offline_verify`, `signature` | The package already carries a transitive seal and its own verifier — the lane only orchestrates | Consumer must implement the four ops | **Seam.** See below. |
| **`oci-native`** | `members`, `root_digest` | When the target is a registry the **OCI image manifest *is* the descriptor list** — `members` = layer descriptors, `root-digest` = manifest digest. No sidecar, sharding native | Only meaningful for the registry target | **Ship as a target-coupled mode.** |
| `frictionless` (`datapackage.json`) | `members` | Good schema story for tabular resources | Oriented at tabular schemas, not arbitrary binary payloads or fixity | Opt-in; poor general fit. |

**The `self-sealing` case is not hypothetical — [vig-os/tessera](https://github.com/vig-os/tessera) is it.** A `.tsra` is an immutable, content-addressed FAIR data product with blake3 hash-on-write, a Merkle-Mountain-Range `content_hash`, and a `manifest_hash` seal that *transitively commits to every block digest plus all metadata*. It signs a JCS-canonical envelope binding `{alg, key_id, manifest_hash, signer, signed_at, key_format}` ([ADR-0037](https://github.com/vig-os/tessera/blob/dev/docs/adr/0037-signing-trust-model.md)), verifies offline with `tessera verify-sig`, and already distributes to the same targets this spike picked: `tessera push`/`pull` carry the signature as a second OCI layer (`application/vnd.tessera.signature.v1+json`), and `tessera publish` deposits into InvenioRDM/Zenodo with a DOI.

Two things that makes obvious:

1. **Wrapping a `.tsra` in a BagIt bag would be actively wrong** — a flat, non-transitive payload manifest laid over a Merkle seal, and a second signature competing with one whose entire design goal is decade-scale offline verification. Any design that hard-codes one package format produces exactly that.
2. **Tessera arrived independently at GitHub Releases + OCI + DOI.** Two unrelated projects converging on the same target set is the strongest evidence in this spike that the target tiers are right — and that the devkit's contribution is orchestration, not format.

Tessera is pre-1.0 with an unfrozen on-disk format and a held first release, so it is a **design constraint today and an adopter later**: the provider seam must exist at v1 of the lane so tessera can plug in without the lane changing.

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
- **(E) Fix one wire package format (just ship BagIt).** Rejected. `vig-os/tessera`'s `.tsra` already carries a Merkle-sealed, self-verifying, independently-signed package; laying a flat BagIt manifest and a second signature over it is a downgrade. The lane must consume a format's own integrity when it has one — hence the provider contract in §4.
- **(F) Give every target its own read-scoped GitHub App.** Rejected as the default. A privileged probe verifies a path no consumer takes, and each App is another installation to keep current and another key to rotate. The probe uses the least authority a consumer would have — none, for a public target. An App stays right for exactly one role: an independent observer that must `issues: write` or watch from another repository (§7).
- **(G) Use `git-lfs` and skip the whole lane.** Rejected on economics — see the spike table. Metered per-clone bandwidth makes the publisher's cost a function of consumer popularity, and LFS storage is append-only across history.

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
- [ ] `DEVKIT_DATA_PACKAGE_FORMAT` selects the wire package provider; `archive+manifest` and `bagit` ship, and a `custom` provider supplying all four ops (`pack`/`members`/`root-digest`/`verify`) runs the lane end to end **without the lane building a manifest or adding a second signature**. A test asserts that a provider declaring `provides: signature` is verified, not re-signed.
- [ ] The lane detects or declares its **regime** (few-large vs many-small) and the docs give the inverted target/confirmation advice for each.
- [ ] Many-small confirmation reads a **committed manifest at a pinned revision** plus sentinels and expected-count assertions — never a tree listing. A test reproduces the >1000-entry tree pagination trap and proves the probe survives it.
- [ ] The lane paces commits against a **global per-repo** budget (HF: 128/hour), not per-job concurrency, and backs off on 429 using `Retry-After`.
- [ ] An orphan-audit op exists and the reconcile lane reports `orphans / total_lfs`.
- [ ] `just data-release-probe-target` measures per-commit latency, directory/file ceilings and commit-rate headroom on a throwaway branch; docs require running it before fixing a layout.
- [ ] Confirmation is **O(1) in artefact size**: each target's probe reads the server-computed digest/state rather than re-downloading the artefact. A test asserts no probe downloads the full artefact.
- [ ] The probe asserts three-way agreement — signed digest == target-reported digest == pack-time digest — and treats a `null`/absent server digest as **unknown**, never as pass.
- [ ] For a sharded artefact, the probe additionally asserts the `root-digest` over the ordered part set; a test proves that a complete set of individually valid parts taken from two different releases **fails**.
- [ ] The GitHub-target upload path retries into the **draft** (asset upload is not resumable), and the job timeout is sized for repeated attempts.
- [ ] Each enabled target has a landing probe that runs after publish and again on the reconcile schedule; a target that published but did not land fails the lane and names itself.
- [ ] Landing probes for **public** targets run **unauthenticated**, and a test asserts no probe is handed a write-scoped credential.
- [ ] The data lane's tag push reuses the existing `COMMIT_APP` credential — no third App is introduced.
- [ ] `just data-release-preflight` validates every enabled target's write credential, its probe path under the probe's own authority, and the downstream workflow's `active` state; the lane runs it as its first job, before any ref moves.
- [ ] Setup **fails** when `DEVKIT_DATA_RELEASE=true` declares a target whose credential is absent — never warns and continues.
- [ ] `docs/DATA_RELEASE.md` exists as SSoT, linked from `RELEASE_CYCLE.md` and `DOWNSTREAM_RELEASE.md`, and carries: the target matrix with its verdicts, the HF + OCI + Zenodo recipes, the signing-backend decision table, the mirror retirement path, the credential/probe-authority rule, the key-rotation runbook stub, and the Zenodo "archives the source tree, not your assets" caveat.
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

- **Beneficiaries:** any devkit consumer that publishes a dataset alongside (or instead of) code. Immediate: `exoma-ch/nucl-parquet` (blocked from adopting today — its data lane is the reason), `vig-os/tessera` (FAIR data products — and the reference `self-sealing` package provider; pre-1.0 today, so it is a **design constraint now, adopter later**), `exoma-ch/talys` and `exoma-ch/theranostics-landscape` (Parquet outputs, no release lane yet).
- **Compatibility:** purely additive. The lane is opt-in via `DEVKIT_DATA_RELEASE`, defaults off, and scaffolds nothing when off. No change to the code train's version model, tag namespace, concurrency group or promote gate. Every existing consumer is byte-identical.
- **Coupling to [#1746](https://github.com/vig-os/devkit/issues/1746):** this issue depends on #1746's §2 (draft-Release-first + the named pre-publish assets window) and should land after it, or share that section. It does **not** depend on #1746's §1 (pre-release format) or §3 (`publish-release-extension.yml`).
- **Sequencing suggestion:** cut §§1–4 (keys, lane, one-operation tagging, integrity) as the MVP; §§5–6 (reconciliation, mirror recipes) as a fast follow-up; the Zenodo/DOI recipe last, since it is the only target with no adopter blocked on it today.

### Changelog Category

Added

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 12:25 PM_

**Amended** — three changes to the body, recorded here so anyone who read the first version sees the delta.

### 1. The wire package is pluggable; BagIt is one provider, not *the* format (§4, and the spike table)

The first draft leaned toward "ship BagIt". That was wrong, and [vig-os/tessera](https://github.com/vig-os/tessera) is why. A `.tsra` is already an immutable, content-addressed data product with blake3 hash-on-write, a Merkle-Mountain-Range `content_hash`, and a `manifest_hash` seal transitively committing to every block digest plus all metadata — with its own signed JCS-canonical envelope ([ADR-0037](https://github.com/vig-os/tessera/blob/dev/docs/adr/0037-signing-trust-model.md)), its own offline verifier, and its own OCI and DOI distribution paths. Wrapping that in a BagIt bag lays a flat, non-transitive manifest over a Merkle seal and puts a second signature next to one designed for decade-scale offline verification. That is a downgrade dressed as diligence.

So §4 is now a **provider contract** — `pack` / `members` / `root-digest` / `verify`, plus a `provides:` declaration — with two rules: the lane signs the root digest and never re-derives integrity a format already supplies, and if a provider declares `signature`, the lane **verifies it and stops** rather than adding a competing one. Five providers listed; the devkit ships `archive+manifest` (default) and `bagit` (recommended for archival/air-gapped), with `oci-native`, `frictionless` and consumer-supplied `self-sealing` as the rest.

Worth noting independently: tessera converged on **GitHub Releases + OCI + DOI** without reference to this spike. Two unrelated projects picking the same target set is the best evidence here that the tiers are right and that the devkit's contribution is orchestration, not format.

Tessera is pre-1.0 with an unfrozen on-disk format, so it is a **design constraint today and an adopter later** — the seam has to exist at v1 of the lane so it can plug in without the lane changing.

### 2. "Did it land?" is a first-class job — and mostly needs *less* authority, not a GitHub App (§7)

Publishing is not landing: a mirror push can 200 and still serve the previous version. Each enabled target now declares a **landing probe** that runs after publish and again on the reconcile schedule.

This is not new machinery. [`docs/CROSS_REPO_RELEASE_GATE.md`](https://github.com/vig-os/devkit/blob/main/docs/CROSS_REPO_RELEASE_GATE.md) already exists to *"validate release artifacts outside the release repository execution context"* and *"keep release orchestration and validation responsibilities separated"* — the data lane reuses that `repository_dispatch` contract instead of inventing a parallel one. Dispatching a consumer's own CI against the landed bytes is the same seam, which is how you get "the clients still work" rather than "the bytes exist".

On whether each target needs its own App: **mostly no, deliberately.**

- **Write paths already have one.** Devkit mandates `COMMIT_APP_*` + `RELEASE_APP_*` with `github.token` explicitly not a fallback. The lane's tag push **reuses the Commit App** — no third credential. [exoma-ch/nucl-parquet#350](https://github.com/exoma-ch/nucl-parquet/pull/350) reached the same conclusion after a bespoke PAT expired mid-release ([#344](https://github.com/exoma-ch/nucl-parquet/issues/344)).
- **Probes should have less authority, not more.** Verifying a *public* artefact with a privileged token exercises a path no consumer will ever take — it passes against an object the public cannot read, a repo whose visibility flipped, a registry whose anonymous-pull policy changed. The probe's job is "can a consumer get this?", so it asks the way a consumer asks: unauthenticated, for every public target. A read secret appears only where the target is genuinely private.
- **One role where an App is right:** an independent observer that must `issues: write`, or that watches from another repo. Even there, check the scope rather than reaching by reflex — nucl-parquet's App installation has no `issues` scope, which is exactly why its reconcile lane runs on `GITHUB_TOKEN`. The documented rule is *confirm the credential actually holds the permission*, not *use the App token*.

### 3. Credentials and preflight are part of **setup**, not of the first release (§8)

- Scaffold-time **refusal**, not a warning: `DEVKIT_DATA_RELEASE=true` with a declared target and no credential fails setup. "Warn and continue" is how [#283](https://github.com/exoma-ch/nucl-parquet/pull/283) shipped two green releases that pushed nothing.
- Provisioning is scripted via the existing [`gh-app-provision`](https://github.com/vig-os/devkit/tree/main/.claude/skills/gh-app-provision) skill, extended to set each enabled target's variable + secret pair.
- `just data-release-preflight` proves, per enabled target: the write credential works, the probe path works **under the probe's own authority**, and the downstream workflow is `active`. Run at adoption, and again as the lane's first job **before any ref moves**.
- The signing-key ceremony (generation, committed public key, rotation runbook) is an adoption-time artefact with a scaffolded doc stub — the first release is the worst moment to discover the committed key and the secret have diverged.

Acceptance criteria extended accordingly, including a test that a provider declaring `provides: signature` is verified rather than re-signed, and a test that no probe is handed a write-scoped credential.

---

Also filed [exoma-ch/nucl-parquet#429](https://github.com/exoma-ch/nucl-parquet/issues/429) — its data lane uploads assets onto an already-published release, so enabling immutable releases 422s every data release *after* the suite has run, the tarball is built and the signing key has been used. The fix there (draft → upload → assert asset set → undraft) is this issue's §3 contract, so that repo moves onto the target shape rather than away from it. That issue also records the adoption position: revisit once this lane has actually shipped and been through a cycle in a consumer repo — until then nucl-parquet stays the reference implementation, and anything the lane cannot express is a gap to report here.


---

# [Comment #2]() by [gerchowl]()

_Posted on September 29, 2026 at 03:13 PM_

**Amended again — §8, "Confirmation at scale".** The first version specified *whether* a release landed but not how you confirm a **big** one without the confirmation becoming the expensive part. Three failure modes only exist at size:

1. a partial upload that reports success — 200 returned, asset row exists, bytes truncated;
2. **confirmation itself becoming expensive** — "download and hash" × N targets × every release is minutes of CI and gigabytes of egress, and a probe that makes releases slow gets disabled;
3. past the per-asset ceiling you ship a **set**, and a set of individually valid parts can still be the *wrong* set.

### Every target already computes a digest server-side — read it, don't re-download

| Target | Confirmation | Cost |
| --- | --- | --- |
| GitHub Releases | `.assets[].state == "uploaded"` + `.assets[].digest == "sha256:<hex>"`, computed by GitHub at upload and immutable ([GA 2025-06-03](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/)). `null` on pre-GA assets → treat as **unknown**, never as pass | 1 API call |
| HF dataset | `repo_info(..., files_metadata=True)` → per-file size + LFS `sha256`; the Xet CAS verifies xorb integrity on ingest and registers the sha256 | 1 API call |
| OCI / ghcr | **Intrinsic** — the registry rejects a blob whose content does not match its digest, so a successful push *is* the confirmation; `oras manifest fetch --descriptor` resolves tag → manifest digest | 1 API call |
| Zenodo | record files' `checksum` (`md5:<hex>`; two independent MD5s stored, one to detect out-of-band modification) | 1 API call |

### The confirmation is a three-way agreement, and it is free

`signed digest == target-computed digest == pack-time digest`.

Verified live against `data-2026.8.5` while writing this:

- minisign trusted comment (covered by the signature): `sha256=938d46e4cef3fa9ec98eb3c4d2a42b5bf36054cd654f843997dc2f81e634647d`
- GitHub REST `.assets[].digest`: `sha256:938d46e4cef3fa9ec98eb3c4d2a42b5bf36054cd654f843997dc2f81e634647d`
- `state: uploaded`, `size: 1014354062`

**967 MiB artefact, confirmed for one API call and a 378-byte signature fetch.** And note which way the strength runs: GitHub's digest is a **third-party computation over the bytes the target actually holds**, so agreement with the signed digest says *the bytes being served are the bytes we signed* — strictly stronger than what a re-download-and-hash probe tests, which is only "our hash of our own file matched".

Corollary for §4: the digest must be bound **into** the signature, not merely shipped alongside it. A sidecar digest confirms nothing against anyone who can replace the artefact, since they can replace the sidecar too.

### Cheap evidence about the *served* bytes

The digest describes the stored object; consumers get a CDN. Range requests work on release downloads — verified: `accept-ranges: bytes`, `HTTP 206`, `content-range: bytes 0-63/1014354062`, served from Azure Blob — so for kilobytes a probe confirms total size, format magic (`28 b5 2f fd` = zstd) and a random middle chunk against the per-file manifest. **Second place the per-file manifest earns its keep** ([nucl-parquet#296](https://github.com/exoma-ch/nucl-parquet/issues/296)): partial verification needs per-file digests to check against.

### Sharding makes confirmation a set property

Past 2 GiB: every part present and `uploaded`, every part digest matching, **and a `root-digest` over the ordered set**. Without the third, a complete set of individually valid parts drawn from *two different releases* confirms perfectly and reassembles into garbage — which is what §4's `root-digest` op is for, and why a provider that already has one (tessera's MMR `content_hash`) needs nothing added.

### Upload mechanics that only bite at size

`hf upload` resumes and skips already-uploaded files; OCI blob upload is chunked and resumable per the distribution spec; **GitHub release asset upload does not resume** — a failed 967 MiB upload restarts from zero. That is a second, independent argument for the draft window (§3): retry into the draft rather than against a frozen release, and size the job timeout for *N* attempts. Probes get their own retry budget so a slow upload cannot eat the confirmation step's runway.

Acceptance criteria extended: probes must be O(1) in artefact size (with a test that none downloads the full artefact), must treat an absent server digest as unknown rather than pass, and a sharded-artefact test must prove that a complete set of valid parts from two different releases **fails**.


---

# [Comment #3]() by [gerchowl]()

_Posted on September 29, 2026 at 03:32 PM_

**Amended — §8 now has a "Two regimes" subsection, and one thing I had wrong is corrected.**

Second motivating adopter: **[morepet/mat-vis](https://github.com/morepet/mat-vis)** — ~3000 PBR materials × channels × tiers ≈ **28k LFS files** per release. It is the *inverse* of nucl-parquet, and it inverts the target choice, the atomicity story and the confirmation mechanism. Its ADR trail and issue history are the best empirical record of the many-small regime I have seen, so most of this is cited rather than reasoned.

### Correction

§8's HF row said confirmation is "one `repo_info(files_metadata=True)` call". **That is wrong at file-count scale.** HF's tree API caps at **1000 entries per page**, and with `recursive=true` *directories count as entries* — at 3000 materials the first page returned 1000 directories and **zero files**. mat-vis's Python client filtered for `type == file`, got nothing, and reported `sources: {}` for a production release that was completely fine ([mat-vis#238](https://github.com/morepet/mat-vis/issues/238)). The smoke tag (~750 entries) fit under the cap, so it passed staging and broke only at production scale. Row corrected and scoped to few-large.

### GitHub Releases is disqualified for many-small on **atomicity**, not size

[ADR-0007](https://github.com/morepet/mat-vis/blob/main/docs/decisions/0007-substrate-move-to-hf-datasets-and-tar-container.md) attributes two bug classes straight to the substrate: dangling rowmap → missing parquet (non-atomic multi-file upload) and index files written at **15 of 1965 entries** (clobber-rather-than-merge across batches). A release assembled from N independently uploaded objects has N chances to be half-published — and per-asset digest confirmation cannot catch an asset that nobody listed.

### HF's real limits are not the documented ones

Probed on a throwaway branch ([`scripts/probe-hf-per-file-limits.py`](https://github.com/morepet/mat-vis/blob/main/scripts/probe-hf-per-file-limits.py), 2026-04-21): 100 files → 3.8 s, 1k → 9.7 s, 5k → 38 s, 10k → 88 s, 25k → ❌ `too many files per directory`. Docs say 25,000 LFS files / 1 GB per commit and suggest 50–100 files per commit for the 60 s HTTP timeout; **the ceiling that actually binds is 10,000 files per _directory_** — a different axis than the documented one, findable only by probing. Plus two production-measured ceilings:

- **Commits: 128/hour, per repo** — `429 … exceeded the rate limit for repository commits (128 per hour)` ([mat-vis#225](https://github.com/morepet/mat-vis/issues/225)). It is a **global per-repo counter**, so per-job `concurrency` groups do not protect it: parallel matrix writers each see headroom and collectively blow the cap.
- **API requests: 1000 / 300 s** rolling.

### Many-small confirmation is O(commits), not O(files)

Not a per-file digest sweep. Read a **committed manifest at a pinned revision** (never rebuild from a tree listing — the three clients that read the manifest passed; only the one rebuilding from the tree broke), plus **sentinels** per unit of work (`.tier_complete`), plus **expected-count assertions** — the failure mode here is silent *incompleteness*, so "are all 1965 listed?" is the question, not "does this file exist?". And an **orphan audit**: a mid-batch crash leaves orphaned LFS blobs with **no documented auto-GC on dataset repos** ([#190](https://github.com/morepet/mat-vis/issues/190), [#221](https://github.com/morepet/mat-vis/issues/221)), so reconcile should report `orphans / total_lfs`.

### Container vs per-file is a real fork, and the answer is empirical

mat-vis chose a tar container in ADR-0007 on **2026-04-19** and reversed it **two days later** in [ADR-0012](https://github.com/morepet/mat-vis/blob/main/docs/decisions/0012-per-file-substrate-drop-tar.md), after a staging bake built a ~70 GB tar that filled a 126 GB disk and wedged mid-write with no durable state. Three generalisable findings:

- **Peak local disk is O(container), not O(payload)** — the same source went from 70 GB to under 1 GB with per-file batching.
- **Batch commits are durable checkpoints** — a crash at material 1500/1993 keeps 1450 committed and resumes at 1451 via a tree-listing preflight. A single container is resumable by construction or not at all.
- **A container defeats Xet deduplication.** Xet's chunk-level CDC dedupes identical bytes across tiers automatically — the same `color.png` at 128/256/512/1k costs one xorb; wrapped in per-tier tars it costs four copies. **On HF, containerising is a storage pessimisation**, the exact opposite of the usual "fewer, larger files are kinder to a hub" intuition.

This is the strongest argument in the spike for §4's provider seam being *a choice with a probe attached* rather than a default: two defensible container decisions, two days apart, same project, reversed by measurement. So the lane ships **`just data-release-probe-target`** — throwaway-branch measurement of per-commit latency, directory/file ceilings and commit-rate headroom — and the docs say run it **before** fixing a layout.

### Also noted

[mat-vis#421](https://github.com/morepet/mat-vis/issues/421) (open): client returns 434 KB for a thumb whose HF `content-length` is 47 KB — a 9× served-vs-expected mismatch. Independent of its root cause, it is a live instance of §8's "the digest describes the stored object; consumers get something else", and an argument for the range-based served-bytes spot check being a real probe rather than a nicety.

Acceptance criteria extended: declare/detect the regime; many-small confirmation reads a committed manifest + sentinels + expected counts with a test reproducing the >1000-entry pagination trap; pace commits against a **global per-repo** budget with `Retry-After` backoff; ship an orphan audit; ship the target probe and require it before fixing a layout.


