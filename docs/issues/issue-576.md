---
type: issue
state: open
created: 2026-06-09T21:33:19Z
updated: 2026-06-09T21:33:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/576
comments: 0
labels: chore, priority:low, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T06:38:21.928Z
---

# [Issue 576]: [[CI] Migrate actions/create-github-app-token from app-id to client-id](https://github.com/vig-os/devcontainer/issues/576)

## Context

Workflow runs (e.g. [Prepare Release #13](https://github.com/vig-os/devcontainer/actions/runs/27237002467)) emit the deprecation warning:

> Input 'app-id' has been deprecated with message: Use 'client-id' instead.

This comes from `actions/create-github-app-token` (v3), which deprecated the `app-id` input in favor of `client-id`. The input still works today (deprecation, not removal), so this is low risk / cosmetic for now.

## Goal

Replace `app-id: ${{ secrets.*_APP_ID }}` with `client-id: ${{ secrets.*_CLIENT_ID }}` across all workflows so the deprecation warning is removed.

## Prerequisite

`client-id` expects the GitHub App's **Client ID** (e.g. `Iv23...`), not the numeric App ID. New secrets (`COMMIT_APP_CLIENT_ID`, `RELEASE_APP_CLIENT_ID`) must be provisioned at the repo/org level **before** switching.

## Scope

Update every `actions/create-github-app-token` usage. Root workflows:
- `.github/workflows/prepare-release.yml`
- `.github/workflows/promote-release.yml`
- `.github/workflows/release.yml`
- `.github/workflows/sync-issues.yml`
- `.github/workflows/sync-main-to-dev.yml`

Templated copies (must stay in sync per single-source-of-truth):
- `assets/workspace/.github/workflows/**`
- `assets/smoke-test/.github/workflows/repository-dispatch.yml`

## Acceptance Criteria

- `*_CLIENT_ID` secrets provisioned.
- No workflow emits the `app-id` deprecation warning.
- Root and `assets/workspace` workflow copies remain consistent.
