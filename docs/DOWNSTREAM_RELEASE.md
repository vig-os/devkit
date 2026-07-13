# Downstream Release Workflows

This document is the **only** place that describes the release process for **consumer projects** that install workflows from `assets/workspace/`. The upstream devcontainer and smoke-test validation flow is documented in [`docs/RELEASE_CYCLE.md`](RELEASE_CYCLE.md) and [`docs/CROSS_REPO_RELEASE_GATE.md`](CROSS_REPO_RELEASE_GATE.md).

## Overview

The downstream template uses a split release architecture:

- `prepare-release.yml` (`workflow_dispatch`) prepares `release/X.Y.Z`
- `release.yml` (`workflow_dispatch`) orchestrates:
  - `release-core.yml` (`workflow_call`)
  - `release-extension.yml` (`workflow_call`, project-owned)
  - `release-publish.yml` (`workflow_call`)
- `promote-release.yml` (`workflow_dispatch`) runs **after** a successful final `release.yml`: validates draft GitHub Release and release PR state, publishes the release, merges `release/X.Y.Z` to `main`, and best-effort cleans up remote git RC tags without a GitHub Release (no GHCR/cosign; see [Promote release (final)](#promote-release-final))

All files are deployed from `assets/workspace/` by `init-workspace.sh`.

On failure, the orchestrator runs a single consolidated rollback that resets the release branch (best-effort), does **not** delete tags (forward-fix policy), and opens a failure issue with forward-fix guidance.

## Release Modes

`release.yml` supports two release modes via `release_kind`:

- `candidate` (default): computes and publishes the next `X.Y.Z-rcN` git tag; optional workflow input **`create-release`** (default `false`) also creates a **draft** GitHub **pre-release**. Use optional `rc-number` to pin `N` when orchestrating from an upstream dispatch (see `docs/CROSS_REPO_RELEASE_GATE.md`). The smoke-test template passes `create-release=true` when it runs the workspace `release.yml` for a candidate.
- `final`: publishes `X.Y.Z`, finalizes `CHANGELOG.md` release date, runs `sync-issues`, and creates a **draft** GitHub Release (publish from the UI when review is complete; aligns with GitHub’s [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and [draft-first guidance](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases#best-practices-for-publishing-immutable-releases))

Candidate mode keeps release branch content unchanged (no CHANGELOG date finalization). Final mode performs changelog finalization before publish.

## Immutable releases, tag rulesets, and forward-fix policy (downstream)

- **Candidate (`X.Y.Z-rcN`)**: By default only the git tag is created. With **`create-release: true`**, `release-publish.yml` creates a **draft** GitHub **pre-release** (`gh release create --draft --prerelease`). Promote-time validation uses `gh api .../releases/tags/<tag>` and inspects `.draft` to ensure the expected draft pre-release exists; see [Cross-repo gate](CROSS_REPO_RELEASE_GATE.md) for upstream enforcement status. With **immutable releases** enabled, **publishing** a pre-release locks the **linked** tag and assets (see [upstream policy](RELEASE_CYCLE.md#immutable-releases-tag-rulesets-and-forward-fix-policy)); iterate with a **new** RC tag.
- **Final (`X.Y.Z`)**: Automation creates a **draft** GitHub Release; **publishing** it (UI or `promote-release.yml`) applies immutable-release lock-in for the linked tag and assets when that setting is enabled. Enable **immutable releases** and **tag rulesets** on each consumer repository (and org policy) as needed; see [Preventing changes to your releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/preventing-changes-to-your-releases).
- **Rollback**: The orchestrator resets the release branch and does **not** delete tags (forward-fix policy); recover with a new RC or a careful final retry per workflow logs.

## Promote release (final)

After final `release.yml` has pushed tag `X.Y.Z` and created a **draft** GitHub Release, run **`promote-release.yml`** (or `just promote-release X.Y.Z` from the devcontainer; dispatches on `release/X.Y.Z` by default) to:

1. **Validate** — semver, draft release for `X.Y.Z`, release PR not draft / approved / CI green
2. **Promote** — `gh release edit --draft=false`
3. **Merge** — merge `release/X.Y.Z` → `main` (triggers `sync-main-to-dev` when configured)
4. **Cleanup** (best-effort, does not fail the workflow) — delete remote git tags matching `${VERSION}-rc*` that have **no** GitHub Release

**Upstream (`vig-os/devcontainer`) only:** Root `promote-release.yml` also prunes GHCR RC package versions via the org Packages API using **`GITHUB_TOKEN`** with **repo Admin** on the `devcontainer` package (one-time **Manage Actions access** grant). See [GitHub App Configuration](RELEASE_CYCLE.md#github-app-configuration) and [Registry and cleanup tokens](RELEASE_CYCLE.md#registry-and-cleanup-tokens-upstream) in `docs/RELEASE_CYCLE.md`.

This template does **not** implement upstream-only steps (GHCR `:latest`, cosign, cross-repo smoke-test gate). Projects that need registry or deploy promotion after merge should run separate automation or extend their `release-extension.yml` / own workflows; see [Extension Hook](#extension-hook).

## Workflow Interface

The orchestrator `release.yml` passes release context directly to the called reusable workflows:

- `.github/workflows/release-core.yml`
- `.github/workflows/release-extension.yml`
- `.github/workflows/release-publish.yml`

There is no separate contract-version handshake; compatibility is defined by the `workflow_call` input schema in each workflow file.

`promote-release.yml` is a standalone `workflow_dispatch` workflow (input: `version`); it does not call the reusable workflows above.

## Toolchain provisioning is mode-aware

Since [#991](https://github.com/vig-os/devkit/issues/991), the whole
release/automation set provisions its toolchain per `DEVKIT_MODE`
(`.vig-os`), following the conditional-`container:` pattern in
[`docs/rfcs/ADR-conditional-container-toolchain.md`](rfcs/ADR-conditional-container-toolchain.md):

- Each `workflow_dispatch`/event-triggered workflow (`release.yml`,
  `prepare-release.yml`, `promote-release.yml`, `sync-issues.yml`,
  `renovate-changelog-build.yml`, `sync-main-to-dev.yml`) runs a leading
  **`resolve-toolchain`** job that reads `.vig-os` and emits `mode`, `image`, and
  `image-tag`. The `image` is the devcontainer image in the container modes
  (`devcontainer`/`both`) and an **explicit empty string** in the host modes
  (`direnv`/`bare`), which makes each downstream `container:` job run directly on
  the runner. `prepare-release.yml` runs the same composite **inline** in its host
  `validate` job and exposes the outputs to the `prepare` job.
- Every job then runs the **`setup-devkit-toolchain`** composite as its first
  step after checkout: it is a no-op-friendly preamble that exports the in-image
  env in the container modes, builds the repo's flake dev-shell in `direnv`, or
  `uv tool install`s the pinned host toolchain (incl. `vig-utils`) in `bare`.
- The orchestrator `release.yml` **resolves once** and threads the result into
  the reusable workflows via the `toolchain_mode`, `toolchain_image`, and
  `devkit_version` `workflow_call` inputs; `release-core.yml` /
  `release-publish.yml` do **not** re-resolve.

This is a toolchain-provisioning change only — the release **choreography** (step
logic, ordering, `workflow_call` inputs/outputs, and rollback semantics) is
unchanged across all modes. Host-mode runners already provide `git`, `gh`, and
`jq`; `just`, `uv`, `prek`, `retry`, and the `vig-utils` release scripts
(`prepare-changelog`, `renovate-changelog-pr`) come from the composite, so the
choreography's bare `run:` invocations are identical in every mode. In `bare`
mode the composite pins `vig-utils` to the `.vig-os` `DEVKIT_VERSION`
(`renovate-changelog-pr` in `renovate-changelog-build.yml`, `prepare-changelog`
in `prepare-release.yml` / `release-core.yml`); see
[`docs/MIGRATION.md`](MIGRATION.md#bare-mode-vig-utils-release-console-scripts).

## Required App Secrets

Downstream repositories are expected to provide both app credentials:

- `COMMIT_APP_ID` (required by `vig-os/sync-issues-action` in `sync-issues.yml`)
- `COMMIT_APP_CLIENT_ID`
- `COMMIT_APP_PRIVATE_KEY`
- `RELEASE_APP_CLIENT_ID`
- `RELEASE_APP_PRIVATE_KEY`

Template behavior relies on explicit app-token generation for release operations:

- use **Commit App** token for protected branch/ref writes (`commit-action`, branch/tag mutation)
- use **Release App** token for release orchestration and PR/release API operations

`github.token` is intentionally not used as a fallback for these release write paths.

## Input Naming Convention

All `workflow_call` inputs use underscores (e.g. `release_kind`, `dry_run`, `git_user_name`). The orchestrator `release.yml` translates its own `workflow_dispatch` hyphenated inputs at each call site.

## Extension Hook

Project-specific release behavior belongs in `.github/workflows/release-extension.yml`.

Default template behavior is no-op. Projects can customize this workflow for tasks such as:

- package publishing
- container publishing
- signing and attestations
- release artifact upload

Extension contract inputs include both `release_kind` and `publish_version`, so custom logic can branch on candidate vs final behavior.

`release.yml` requires extension success before publish, so extension failures block release publication.

## Cross-Repo Validation Gate

Cross-repository validation gate details are documented in `docs/CROSS_REPO_RELEASE_GATE.md`.

### Example: GHCR Publishing

The following shows how a downstream project could customize `release-extension.yml` to build and push a container image to GHCR:

```yaml
name: Release Extension

on:
  workflow_call:
    inputs:
      version:
        required: true
        type: string
      finalize_sha:
        required: true
        type: string
      release_date:
        required: true
        type: string
      release_kind:
        required: true
        type: string
      publish_version:
        required: true
        type: string
jobs:
  ghcr-publish:
    name: Publish Container Image
    runs-on: ubuntu-22.04
    permissions:
      contents: read
      packages: write
    steps:
      - name: Checkout finalized commit
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.finalize_sha }}

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ inputs.publish_version }}
            ${{ inputs.release_kind == 'final' && format('ghcr.io/{0}:latest', github.repository) || '' }}
```

## Upgrade Path

1. Upgrade downstream devcontainer version (which redeploys `assets/workspace` templates).
2. Keep project-owned `release-extension.yml` (preserved on force upgrades).
3. Ensure project-owned `release-extension.yml` matches the current `workflow_call` inputs used by `release.yml`.
4. Run `prepare-release` / `release` in `--dry-run` mode to validate integration.

## Pinning and Drift

Release workflow logic is centralized in shipped local reusable workflows (`release-core.yml`, `release-publish.yml`) while extension logic remains project-owned (`release-extension.yml`).

This reduces drift in release safety checks while preserving downstream customization boundaries.
