---
type: issue
state: closed
created: 2026-03-25T13:26:15Z
updated: 2026-03-25T14:48:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/441
comments: 0
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:33.498Z
---

# [Issue 441]: [[BUG] Downstream smoke-test RC tag number does not match upstream](https://github.com/vig-os/devcontainer/issues/441)

## Description

When upstream `vig-os/devcontainer` publishes a candidate (e.g. `0.3.1-rc21`) and dispatches to `devcontainer-smoke-test`, the downstream release workflow creates `0.3.1-rc1` instead of matching the upstream tag. The final release gate in upstream `release.yml` expects a downstream pre-release at the same RC tag and will 404 otherwise.

## Steps to Reproduce

1. Publish an upstream RC after several prior RCs (e.g. `0.3.1-rc21`).
2. Let smoke-test `repository_dispatch` orchestration run `release.yml` on the smoke-test repo.
3. Inspect tags/releases on `vig-os/devcontainer-smoke-test`.

## Expected Behavior

Downstream tag and GitHub Release should use the same RC number as the upstream dispatch (`0.3.1-rc21`).

## Actual Behavior

Downstream auto-increments from local tags only, producing `0.3.1-rc1` when no prior RC tags exist there.

## Environment

- GitHub Actions, `repository-dispatch.yml` + workspace `release.yml` / `release-core.yml`

## Changelog Category

Fixed

## Possible Solution

Pass optional `rc-number` from dispatch payload through `repository-dispatch.yml` into downstream `release.yml` / `release-core.yml`; when set, use it instead of scanning tags for the next RC.

- [ ] TDD compliance (see .cursor/rules/tdd.mdc)
