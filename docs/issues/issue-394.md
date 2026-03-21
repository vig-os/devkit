---
type: issue
state: closed
created: 2026-03-20T09:10:15Z
updated: 2026-03-20T10:19:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/394
comments: 0
labels: bug, area:ci, area:workflow, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:45.537Z
---

# [Issue 394]: [[BUG] Harden downstream release workflows used by smoke-test dispatch](https://github.com/vig-os/devcontainer/issues/394)

## Description
Copilot comments on downstream smoke-test PR #43 highlighted workflow risks. Re-evaluating against the current local downstream-dispatch implementation shows several issues are still valid and actionable.

Primary risk areas:
- Container jobs running `git` without `safe.directory`
- Reusable workflow permission ceilings causing token scope mismatches
- Rollback job container image depending on `core` outputs that may not exist on early failure
- Stale dispatch workflow documentation referencing removed workflows

## Steps to Reproduce
1. Trigger smoke-test downstream orchestration via `repository_dispatch`.
2. Trigger release workflows through `assets/smoke-test/.github/workflows/repository-dispatch.yml`.
3. Exercise failure paths where `core` can fail before producing outputs.
4. Observe potential failures in rollback startup, permission-scoped `gh` calls, or git operations in containerized jobs.

## Expected Behavior
Downstream release/sync workflows execute reliably in containerized jobs, reusable workflows have sufficient minimal permissions, rollback always starts on failure, and dispatch workflow comments match actual workflow set.

## Actual Behavior
Current workflow definitions still contain reliability gaps and drift:
- Missing `safe.directory` in container jobs that run git.
- Caller/job permissions may cap reusable workflow token capabilities.
- Rollback container image is coupled to `needs.core.outputs.image_tag`.
- Dispatch header still references removed `ci-container.yml`.

## Environment
- Repository: `vig-os/devcontainer`
- Downstream dispatch template: `assets/smoke-test/.github/workflows/repository-dispatch.yml`
- Referenced workspace workflows: `assets/workspace/.github/workflows/*.yml`
- GitHub Actions: `ubuntu-22.04`, containerized jobs (`ghcr.io/vig-os/devcontainer:<tag>`)

## Possible Solution
Address in one focused patch set:
- Add `git config --global --add safe.directory "$GITHUB_WORKSPACE"` in container jobs that execute git:
  - `assets/workspace/.github/workflows/release.yml` (`rollback`)
  - `assets/workspace/.github/workflows/release-core.yml` (`validate`)
  - `assets/workspace/.github/workflows/release-publish.yml` (`publish`)
  - `assets/workspace/.github/workflows/sync-main-to-dev.yml` (`check`, `sync`)
- Add explicit caller/job permissions for reusable workflows and `gh` operations:
  - `release.yml` caller jobs (`core`, `publish`)
  - `release-core.yml` jobs requiring `pull-requests` / `actions` scopes
- Decouple rollback container bootstrap from `needs.core.outputs.image_tag` so rollback can start after early `core` failure.
- Update stale comment in `assets/smoke-test/.github/workflows/repository-dispatch.yml` that references `ci-container.yml`.
- Optional hardening: align `prepare-release.yml` with `resolve-image` action and add retry for image manifest validation.

## Related Issues
- Related to #392 (smoke-test dispatch failure context)

## Changelog Category
Fixed

## Acceptance Criteria
- [ ] Containerized jobs that run git configure `safe.directory` consistently.
- [ ] Reusable workflow caller/job permissions are explicitly set to the minimal required scopes.
- [ ] Rollback starts even when `core` fails before output emission.
- [ ] Dispatch workflow comments no longer reference removed workflows.
- [ ] Optional: `prepare-release` image resolution/validation behavior is aligned with shared `resolve-image` conventions.
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
