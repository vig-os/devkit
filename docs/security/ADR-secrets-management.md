# ADR: Secrets-management pattern — sops-nix/age + OIDC

- **Status:** Accepted (pattern / design record; not a migration)
- **Issue:** [#780](https://github.com/vig-os/devkit/issues/780)
- **Source:** PR [#670](https://github.com/vig-os/devkit/pull/670) roadmap, thread D
- **Related:** [#786](https://github.com/vig-os/devkit/issues/786) — agent
  secret-management *behaviour* standard (complementary, see
  [Relationship to #786](#relationship-to-786))

This record fixes **how secrets are stored and delivered** for this repo and its
downstream consumers. It ships the *pattern*, an inert reference example, and a
concrete next-step recommendation — **not** a live sops-nix rollout.

## Context

Two distinct classes of secret exist, and they want different tools:

1. **Runtime / downstream-consumer secrets** — a value a machine (a NixOS host,
   a home-manager user, a consumer's dev environment) must decrypt and use at
   activation/runtime (e.g. an API token a service reads at start-up). The pain
   today is the "per-repo GitHub-secret dance": every consumer re-encrypts and
   re-stores the same secret in their own CI/host out of band.
2. **Cloud / registry authentication** — a workflow proving its identity to an
   external system (a container registry, a cloud provider) so it can push or
   deploy. Historically this is a long-lived stored token.

### Current landscape (cited)

The repo is **greenfield for sops**: there is no `sops`, `age`, or `sops-nix`
anywhere in the tree today.

**Already correct — GHCR via `GITHUB_TOKEN` (no stored secret):** same-repo GHCR
login uses the job's automatic token, so nothing is stored or rotated:

- `.github/workflows/nix-image.yml:143-147` and `:205-209`
  (`docker/login-action` … `password: ${{ github.token }}`)
- `.github/workflows/release.yml:968-972` (same), and
  `.github/workflows/promote-release.yml:106`.

**Existing OIDC precedent (the real lever, already in use):** the `publish` job
requests an OIDC identity token and uses it for **keyless** signing and
provenance — no signing key is stored:

- `.github/workflows/release.yml:864-866`
  (`id-token: write` / `attestations: write` / `artifact-metadata: write`)
- `.github/workflows/release.yml:1109` (`cosign sign --yes` — keyless via OIDC)
- `.github/workflows/release.yml:1127` (`actions/attest-build-provenance`)
- `.github/workflows/scorecard.yml:30` (`id-token: write` for the Scorecard API)

**Stored secrets in use today:**

| Secret | Where (file:line) | Purpose |
|--------|-------------------|---------|
| `CACHIX_AUTH_TOKEN` | `ci.yml:91,128,155,185`, `nix-cachix.yml:58`, `nix-image.yml:87`, `security-scan.yml:62`, `release.yml:767,827` | Push the Nix closure to the `vig-os` Cachix binary cache |
| `RELEASE_APP_CLIENT_ID` / `RELEASE_APP_PRIVATE_KEY` | `release.yml:484`, `prepare-release.yml:169`, `promote-release.yml:219`, `sync-main-to-dev.yml:160` | GitHub App creds → short-lived installation token for PR/label/release ops |
| `COMMIT_APP_CLIENT_ID` / `COMMIT_APP_PRIVATE_KEY` / `COMMIT_APP_ID` | `release.yml:491`, `prepare-release.yml:162`, `renovate-changelog-commit.yml:34`, `sync-issues.yml:84,130`, `sync-main-to-dev.yml:128` | GitHub App creds → short-lived installation token for least-privilege commit/ref identity |

## Decision — the pattern

1. **Runtime / downstream-consumer secrets → sops-nix + age.**
   Secrets are stored **encrypted in git** (`sops` with an `age` key group). Each
   *consumer* holds their own `age` private key (or an `ssh-to-age`-derived host
   key); they decrypt locally with **no shared GitHub secret and no re-storing**.
   On NixOS/home-manager, `sops-nix` decrypts at activation into
   `/run/secrets/<name>` with the declared owner/mode. Adding a consumer =
   appending their **public** `age` recipient to `.sops.yaml` and re-encrypting —
   a public-key operation, not a secret hand-off.

2. **Cloud / registry authentication → OIDC (Workload Identity Federation).**
   For any external registry or cloud, the workflow requests a short-lived GitHub
   OIDC token (`id-token: write`) and federates it — **zero stored credential,
   nothing to rotate or leak**. This is the same mechanism already powering
   keyless `cosign` here; extend it, do not add a stored registry PAT.

3. **GitHub App installation tokens → keep as-is.**
   `RELEASE_APP_*` / `COMMIT_APP_*` are the correct model: the App private key is
   a stored secret, but it mints short-lived, least-privilege **installation
   tokens** scoped per job. GitHub Apps are not an OIDC-federatable identity, so
   the private key stays a GitHub secret — this is by design, not debt.

## Honest trust-model analysis

The reviewer-required caveat: **sops-nix does not eliminate the GitHub secret on
hosted runners — it relocates the root of trust.**

- **On a consumer's own machine**, sops-nix is a genuine win: the private `age`
  key never leaves that machine; the encrypted secret rides along in git; no
  central secret store is trusted. This is where the "no per-repo GitHub-secret
  dance" payoff is real.
- **In CI on GitHub-hosted runners**, the runner is ephemeral and holds no key of
  its own. To decrypt in CI you must hand it an `age` private key — which itself
  has to come from a **GitHub secret** (e.g. `SOPS_AGE_KEY`). So SOPS collapses
  *N* per-value secrets into **one bootstrap key**, but it does **not** reach
  zero stored secrets. It trades many secrets for one (a real blast-radius and
  hygiene improvement) — nothing more.
- **OIDC is the only true no-stored-secret lever.** The credential is minted
  per-job from the workflow's identity and expires in minutes; there is nothing
  at rest to steal. That is why cloud/registry auth is the class where the
  biggest security win lives, and why we already use it for signing.

**Rule of thumb:** encrypted-at-rest data with a per-consumer key → sops-nix/age;
proving identity to an external system → OIDC; a stored key you cannot avoid
(GitHub App) → keep it minimal, least-privilege, and short-token.

## Per-secret classification

| Secret | OIDC? | sops-nix/age? | Keep as GH secret? | Rationale |
|--------|:-----:|:-------------:|:------------------:|-----------|
| GHCR login (`github.token`) | n/a (already tokenless) | no | **already correct** | Same-repo GHCR via the automatic job token — no stored secret exists to retire |
| cosign signing / provenance | **yes (in use)** | no | no | Keyless via `id-token: write` — already the target state |
| `CACHIX_AUTH_TOKEN` | not today | no | **keep (for now)** | Cachix has **no native GitHub-OIDC auth** as of 2026-07; retire only by moving to a self-hosted cache (S3/GCS) reachable via cloud OIDC. Best single candidate to revisit |
| `RELEASE_APP_*` | no | no | **keep** | GitHub App private key → short-lived installation token; not OIDC-federatable by design |
| `COMMIT_APP_*` | no | no | **keep** | Same GitHub App model, least-privilege commit identity |

## Concrete "now" lever

Being honest about the incremental win **today**:

- GHCR is already tokenless; cosign is already keyless. So OIDC retires
  **zero** *current* stored secrets outright — the low-hanging fruit is already
  picked.
- The GitHub App keys **must** stay (by design).
- Therefore the value of this decision is mostly **preventive and forward**:
  1. **Never introduce a stored registry/cloud credential.** The moment we
     publish to an external registry (Docker Hub, GHCR of another org, a cloud
     artifact registry) or deploy to a cloud, wire **OIDC federation** — do not
     add a PAT/JSON-key secret. Extend the existing `id-token: write` pattern.
  2. **`CACHIX_AUTH_TOKEN` is the one realistic migration target.** It cannot go
     to OIDC while on Cachix, but a future self-hosted binary cache on S3/GCS
     *could* authenticate via cloud OIDC, retiring the token. Track separately;
     do not action here.
  3. **Adopt sops-nix/age for downstream-consumer runtime secrets** when the
     first such secret appears, using the reference example below — starting from
     the honest CI caveat (one `SOPS_AGE_KEY` bootstrap secret if CI must
     decrypt; consumers use their own keys locally).

No workflow is modified by this ADR.

## Reference example (inert)

A minimal, clearly-marked, **non-functional** sops-nix + age example lives at
[`docs/security/examples/sops-nix/`](./examples/sops-nix/). It is illustrative
only — placeholder `age` recipients, a plaintext (never-encrypted) example
payload, and a documented Nix module wiring. It is **not** imported by the flake,
image, or any release path and must never be. See its
[`README.md`](./examples/sops-nix/README.md).

## Relationship to #786

This ADR is the **plumbing** layer (how secrets are stored/delivered);
[#786](https://github.com/vig-os/devkit/issues/786) is the **agent-behaviour
/ governance** layer (how an agent must behave around a secret once it exists —
discovery, redaction, exfiltration guardrails, never committing key material).
They **compose and do not overlap**:

- This ADR says: encrypt-at-rest with sops-nix/age; federate with OIDC; keep App
  tokens. It defines the *approved channels* (env / secret store / OIDC) that
  #786 tells agents to treat as the only legitimate secret surfaces.
- #786 says: whatever the channel, an agent must never echo, commit, or exfiltrate
  the decrypted value. This ADR's inert-example discipline (no real key material
  in git) is exactly the behaviour #786 codifies.

Neither restates the other (SSoT): #786 should reference this ADR for the storage
model; this ADR references #786 for agent obligations.

## Consequences

- **Positive:** one documented pattern for both secret classes; the biggest
  security lever (OIDC) is named and already partly realised; downstream
  consumers get a copy-able sops-nix/age example without a shared-secret dance;
  the honest CI caveat is on record so nobody over-claims "no secrets".
- **Negative / accepted:** no secret is retired *today*; `CACHIX_AUTH_TOKEN`
  remains until a cache migration; introducing sops-nix later still needs one CI
  bootstrap key if CI must decrypt.

## References

- `Mic92/sops-nix` — <https://github.com/Mic92/sops-nix>
- `getsops/sops` — <https://github.com/getsops/sops>
- `FiloSottile/age` — <https://github.com/FiloSottile/age>
- GitHub OIDC / hardening deployments —
  <https://docs.github.com/en/actions/concepts/security/openid-connect>
- Existing OIDC use in this repo: `release.yml:864-866,1109,1127`,
  `scorecard.yml:30`
- `docs/CONTAINER_SECURITY.md` — CVE/patching posture (sibling security doc)
