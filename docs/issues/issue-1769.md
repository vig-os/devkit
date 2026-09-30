---
type: issue
state: open
created: 2026-09-29T15:35:21Z
updated: 2026-09-29T15:54:19Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1769
comments: 2
labels: discussion, area:workspace, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: 1770, 1771, 1772, 1773, 1774, 1775, 1776, 1778, 1787
synced: 2026-09-30T08:17:44.688Z
---

# [Issue 1769]: [[SPIKE] Turnkey publish lanes: 2026 best practice per channel, so no repo reinvents its release publishing](https://github.com/vig-os/devkit/issues/1769)

## Motivation / why

Today every repo that ships anything other than a git tag + GitHub Release reinvents its publish lane. scitadel hand-wrote five workflows ([scitadel#208](https://github.com/vig-os/scitadel/pull/208)), tessera would rediscover the same shape ([tessera#441](https://github.com/vig-os/tessera/issues/441)), and nothing exists at all for npm. #1746 (merged on `dev` via #1750) established the *seams* — draft-Release-first owner, pre-publish assets window, standalone `publish-release-extension.yml` on `release: published` — but every seam is a **no-op a consumer must fill by hand**.

**Goal:** a repo declares which channels it publishes to, and devkit scaffolds **and keeps upgrading** a lane that meets the 2026 industry bar for that channel (keyless/OIDC auth, provenance attestations, immutability, idempotent retries, prerelease handling). Adopting a channel should be "declare + one-time registry registration", not "copy a recipe and maintain it forever".

This issue is the **spike umbrella**: one sub-issue per channel researches the current best practice and answers *what devkit should own vs. leave to the repo*. The spikes produce decisions, not code; implementation issues follow per channel.

## Decision / proposed approach (best guess — reviewers should refute)

1. **Declaration, evidence-seeded.** A `.vig-os` key (strawman: `DEVKIT_PUBLISH=crates,pypi,npm,oci,nix,binaries`) — same contract as `DEVKIT_LANGUAGES`: a *declaration* the scaffold seeds from evidence (`Cargo.toml` without `publish = false`, `pyproject.toml` with a build backend, `package.json` without `"private": true`, …), never a detection cache. Per the smallest-denominator rule (#1519), undeclared channels ship nothing.
2. **Managed, not seeded, for the publish mechanics.** The per-channel publish logic (auth, idempotency precheck, attestations, prerelease routing) is devkit-managed and regenerated on upgrade, so security fixes propagate via `devkit-upgrade`. The *build* stays project-owned via `justfile.project` recipes (e.g. `just dist-pypi`, `just dist-npm`), matching how CI already delegates to project recipes.
3. **Two windows, as #1746 defined:** things that belong *on* the GitHub Release (binaries, wheels, SBOM, checksums, attestations) go in the pre-publish assets window; irreversible outward publishes (registries, caches) go after `release: published`.
4. **Uniform per-channel contract:** Trusted Publishing / OIDC wherever the registry supports it (no long-lived tokens), provenance attestation, idempotent "skip if the registry already has this version" precheck, `workflow_dispatch` retry by tag, explicit prerelease policy (publish RCs or not, and under which dist-tag / version spelling).

## What already exists

- `assets/workspace/.github/workflows/release-publish.yml` (managed) — tag + draft GitHub Release; on `dev` draft-first ordering (#1746).
- `assets/workspace/.github/workflows/release-extension.yml` (seeded, no-op) — pre-tag build/sign seam; token ceiling `packages:write, id-token:write, attestations:write` (#1144).
- `assets/workspace/.github/workflows/publish-release-extension.yml` (on `dev`, seeded, no-op) — post-publish seam; stub mentions `crates-io-auth-action` / `gh-action-pypi-publish`.
- `docs/DOWNSTREAM_RELEASE.md` (on `dev`) — "Pre-publish assets window", "cargo-dist adopter recipe", "Publish Extension Hook", GHCR example.
- devkit's own `.github/workflows/release.yml` — cosign keyless signing, SPDX SBOM, `actions/attest-build-provenance` for the GHCR image; `nix-cachix.yml` for the Nix cache. **The upstream already does most of the 2026 bar for OCI + Nix; consumers get none of it.**
- Related: #1748 (Rust L6 seam templates), #1754 (data release lane / mirror targets), #1523 (org stack matrix — the spike verdicts belong there as dated rows), #1519 (smallest denominator), #1496 (Rust pack).

## Scope

**P0 — one spike per channel (sub-issues)**
- [ ] GitHub Releases & release assets (checksums, SBOM, attestations, immutability)
- [ ] crates.io
- [ ] PyPI (incl. PyO3/maturin wheels)
- [ ] npm
- [ ] Prebuilt binaries & installers (cargo-dist, goreleaser-class tools, Homebrew)
- [ ] OCI images (GHCR)
- [ ] Nix binary caches (Cachix / FlakeHub / attic)

**P1 — cross-cutting verdict**
- [ ] Declaration key shape and evidence rules
- [ ] Managed-vs-seeded split, and where OIDC subject binding forces a fixed top-level workflow filename
- [ ] Prerelease policy matrix (per channel: publish RCs? how spelled? which tag?)

**P2**
- [ ] Dated rows in the #1523 stack matrix for every channel verdict
- [ ] ADR in `docs/rfcs/` capturing the decision

## Pitfalls

- **OIDC subject binding vs. reusable workflows.** crates.io and PyPI Trusted Publishing bind to the *workflow file path*; a devkit-managed reusable workflow may not be registrable, and renaming a managed file later silently breaks every consumer's registry registration. The filename is a forever-contract.
- **Irreversibility asymmetry.** A GitHub Release is abandonable while draft; crates.io / PyPI / npm versions are burned the moment they publish. RC policy must not burn final version numbers.
- **Version spelling.** One train version must map to SemVer (`1.2.3-rc.1`), PEP 440 (`1.2.3rc1`), npm dist-tags, OCI tags — interacts with `DEVKIT_PRERELEASE_FORMAT` (#1746).
- **Approval gates.** GitHub `environment:` required reviewers add a second human approval, contradicting the "single approval = release PR" rule in `docs/RELEASE_CYCLE.md`.
- **Speculative defaults.** Shipping all channels to every repo repeats the #1519 anti-pattern; declared-only.
- **Token triggering.** Anything that publishes the Release with `GITHUB_TOKEN` never fires `release: published` (the cargo-dist trap).

## Acceptance criteria

- [ ] Every channel sub-issue closed with a dated verdict: 2026 best practice, gap vs. devkit today, and a concrete "devkit owns X / repo owns Y" split
- [ ] Cross-cutting verdict on declaration key, managed-vs-seeded split, prerelease matrix
- [ ] Implementation issues filed per channel (or explicit "won't do" with reason)
- [ ] ADR drafted

## References

#1746, #1748, #1754, #1523, #1519, #1496, #1144, #988 · `docs/DOWNSTREAM_RELEASE.md` · `docs/RELEASE_CYCLE.md` · `docs/rfcs/ADR-capability-modules.md`

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:42 PM_

## Round-1 consolidation (8 fresh-context reviews: 7 channel specialists + 1 platform architect, 2026-09-29)

Per-channel findings with sources are in comments on #1770–#1776.

### Where all reviewers agree

1. **Registry Trusted Publishing (crates.io, PyPI, npm) binds to the top-level caller workflow filename; reusable workflows cannot be the publisher.** The managed registry lane must therefore be a **top-level file in each consumer, and its filename is a forever contract**. Renaming it breaks every registration at every registry, and `devkit-upgrade` cannot re-register.
2. **Publish mechanics are managed; builds are repo-owned** (`just dist-*`). All seven channel reviewers reached this split independently. It also means #1748 should change from seeded to managed.
3. **No long-lived registry tokens anywhere Trusted Publishing exists.** npm revoked classic tokens on 2025-12-09. Homebrew taps (no OIDC) use an App installation token, and Cachix (no OIDC) keeps a per-repo token.
4. **Checksums and provenance are a generic devkit step over all Release assets**, not per-tool. Assets arrive from several workflows, so this step needs an explicit fan-in before promote.
5. **Every publish is idempotent** (skip versions the registry already has) and can be retried with `workflow_dispatch` by tag.

### Where they disagree, and the proposed resolution

| Question | Positions | Proposal |
|---|---|---|
| One file or one per channel | Architect: a single `publish-release.yml` with a job per channel. npm/PyPI reviewers: `publish-npm.yml`, `publish-pypi.yml`, … | **One managed `publish-release.yml`.** It is one forever-contract name instead of N. Each channel job is gated on `DEVKIT_PUBLISH`, and each job body is a devkit-owned **composite action**, which keeps the caller's OIDC identity while still centralising fixes. `workflow_dispatch` takes `tag` plus an optional `channel` input. |
| OCI mechanism | OCI reviewer: a devkit **reusable** workflow is fine | **Agree, as an exception.** No registry Trusted Publishing is involved, and the cosign/Fulcio identity then binds to devkit's reusable path, giving one stable identity for admission policies. That path is also frozen. |
| Nix | Nix reviewer: this is CI infrastructure, not a publish channel | **Agree.** Move the cache push into the pre-publish window (as upstream does), keep it out of `DEVKIT_PUBLISH`, and skip FlakeHub. |
| `environment:` gates | Would add a second approval, conflicting with the single-approval rule | **An environment with no reviewers**, restricted by deployment rule to tag refs. That gives the registries an OIDC `environment` claim to bind against without adding a human. UNVERIFIED: whether the scaffold can assert it via API; needs a probe. |
| Where the checksum/attestation seal runs | GH reviewer: before promote, never at tag time | **As the first job of `promote-release.yml`.** Promote is already the natural fan-in: a human dispatches it once all assets are on the draft. Asset producers attest their own build provenance; promote writes and attests `SHA256SUMS` and **refuses to undraft** if any asset lacks an attestation. |

### Prerelease matrix (divergent by design)

| Channel | Release candidates |
|---|---|
| GitHub Release | draft pre-release when `create-release: true` (unchanged) |
| crates.io | **off** by default (permanent, never resolved by `^`); opt-in, dotted `rc.N` |
| PyPI | **on**, as production prereleases (`1.2.3rc1`); not TestPyPI |
| npm | **on**, `--tag next`; never `latest` |
| OCI | **on**, `X.Y.Z-rcN` tags, pruned on promote; floating tags only after publish |

### Pitfalls added to the original list

- **The first publish is manual on crates.io and npm.** PyPI has pending publishers; the others have no equivalent. Adoption therefore has a one-time human bootstrap per package, and the runbook must say so.
- **`DEVKIT_PRERELEASE_FORMAT` values can be unmappable** to PEP 440 (`nightly.YYYYMMDD.N`, bare `beta`). The PyPI lane must refuse or normalise them before publish.
- crates.io allows **5 new crates, then 1 per 10 min**, so greenfield workspaces need a staged first publish.
- `actions/attest*` v4+ also needs **`artifact-metadata: write`**; release-candidate pruning on GHCR needs `packages: admin`.
- The wheel or crate uploaded to the Release must be **the same bytes** as the one published to the registry.
- **Adoption over a hand-written `publish-release-extension.yml`:** scaffold the managed file alongside it, fail a preflight if both publish the same channel, and never rewrite the repo-owned file.

### Proposed implementation order

1. **Release seal** (#1770): checksums, attestation gate in promote, ruleset/immutable preflight. Every other channel relies on it.
2. **`publish-release.yml` skeleton**, `DEVKIT_PUBLISH` declaration + evidence rules, and composite-action layout; freeze the filename in an ADR.
3. **PyPI** (#1772) and **crates.io** (#1771, absorbs #1748). tessera and scitadel are concrete adopters.
4. **OCI** (#1775): extract upstream's lane into the reusable workflow.
5. **npm** (#1773) and a separate **GitHub Action / Marketplace** seed.
6. **Binaries** (#1774): managed wrapper now; shrinks once cargo-dist#2521 lands.
7. **Nix** (#1776): CI cache seed plus release-cache push (not a `DEVKIT_PUBLISH` channel).

**Biggest risk (architect):** the managed filename becomes an org-wide single point of failure. Mitigations: freeze it in an ADR; add a `publish-preflight` that fails closed when the registered subject drifts; allow no breaking change to that file.


---

# [Comment #2]() by [gerchowl]()

_Posted on September 29, 2026 at 03:54 PM_

**Status:**

- **ADR:** [#1785](https://github.com/vig-os/devkit/pull/1785) `docs/rfcs/ADR-publish-lanes.md`, status *proposed*. It was revised after an adversarial second review, and all 4 blockers and 8 findings are addressed; see the ADR's "Revisions after review" section.
- **Implementation issues:**
  - #1786 asset builder · #1777 seal
  - #1778 `publish-release.yml` foundation
  - #1779 PyPI · #1748 crates.io
  - #1780 OCI
  - #1781 npm · #1782 GitHub Action
  - #1783 binaries
  - #1784 Nix
  - #1787 candidate publishing (deferred)
- **Main changes from the round-1 consolidation:**
  - v1 registry publishing is **finals only**; candidates need a trigger the train lacks.
  - Environments are renamed `publish-{pypi,crates,npm}`, allow default-branch retries, and are never modified once they exist.
  - The seal runs `validate → seal → promote`, verifies signer and predicate, and has a degrade mode for private repos without Enterprise Cloud.
  - A new managed asset builder owns the bytes on the Release.

The channel spikes (#1770–#1776) close when the ADR is accepted.

