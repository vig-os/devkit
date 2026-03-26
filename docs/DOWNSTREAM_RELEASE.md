# Downstream Release Workflows

This document is the **only** place that describes the release process for **consumer projects** that install workflows from `assets/workspace/`. The upstream devcontainer and smoke-test validation flow is documented in [`docs/RELEASE_CYCLE.md`](RELEASE_CYCLE.md) and [`docs/CROSS_REPO_RELEASE_GATE.md`](CROSS_REPO_RELEASE_GATE.md).

## Overview

The downstream template uses a split release architecture:

- `prepare-release.yml` (`workflow_dispatch`) prepares `release/X.Y.Z`
- `release.yml` (`workflow_dispatch`) orchestrates:
  - `release-core.yml` (`workflow_call`)
  - `release-extension.yml` (`workflow_call`, project-owned)
  - `release-publish.yml` (`workflow_call`)

All files are deployed from `assets/workspace/` by `init-workspace.sh`.

On failure, the orchestrator runs a single consolidated rollback that resets the release branch (best-effort), does **not** delete tags (forward-fix policy), and opens a failure issue with forward-fix guidance.

## Release Modes

`release.yml` supports two release modes via `release_kind`:

- `candidate` (default): computes and publishes the next `X.Y.Z-rcN` tag as a GitHub pre-release (or use optional `rc-number` to pin `N` when orchestrating from an upstream dispatch; see `docs/CROSS_REPO_RELEASE_GATE.md`)
- `final`: publishes `X.Y.Z`, finalizes `CHANGELOG.md` release date, runs `sync-issues`, and creates a **draft** GitHub Release (publish from the UI when review is complete; aligns with GitHub’s [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and [draft-first guidance](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases#best-practices-for-publishing-immutable-releases))

Candidate mode keeps release branch content unchanged (no CHANGELOG date finalization). Final mode performs changelog finalization before publish.

## Immutable releases, tag rulesets, and forward-fix policy (downstream)

- **Candidate (`X.Y.Z-rcN`)**: `release-publish.yml` creates a **published** GitHub **pre-release** for the RC tag. With **immutable releases** enabled, **publishing** that pre-release locks the **linked** tag and assets (see [upstream policy](RELEASE_CYCLE.md#immutable-releases-tag-rulesets-and-forward-fix-policy)); iterate with a **new** RC tag.
- **Final (`X.Y.Z`)**: Automation creates a **draft** GitHub Release; a human **publishes** it from the Releases UI when ready—**publishing** applies immutable-release lock-in for the linked tag and assets when that setting is enabled. Enable **immutable releases** and **tag rulesets** on each consumer repository (and org policy) as needed; see [Preventing changes to your releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/preventing-changes-to-your-releases).
- **Rollback**: The orchestrator resets the release branch and does **not** delete tags (forward-fix policy); recover with a new RC or a careful final retry per workflow logs.

## Workflow Interface

The orchestrator `release.yml` passes release context directly to the called reusable workflows:

- `.github/workflows/release-core.yml`
- `.github/workflows/release-extension.yml`
- `.github/workflows/release-publish.yml`

There is no separate contract-version handshake; compatibility is defined by the `workflow_call` input schema in each workflow file.

## Required App Secrets

Downstream repositories are expected to provide both app credentials:

- `COMMIT_APP_ID`
- `COMMIT_APP_PRIVATE_KEY`
- `RELEASE_APP_ID`
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
