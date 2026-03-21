---
type: issue
state: open
created: 2026-03-20T13:20:04Z
updated: 2026-03-20T13:20:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/398
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:44.565Z
---

# [Issue 398]: [[BUG] sync-main-to-dev PR does not trigger CI in downstream repos](https://github.com/vig-os/devcontainer/issues/398)

### Description

The `sync-main-to-dev.yml` workflow (workspace template) creates a PR targeting `dev`, but the `ci.yml` workflow is never triggered on the resulting PR. Since branch protection rulesets require "CI Summary" to pass, the sync PR is permanently blocked from merging.

### Steps to Reproduce

1. Push to `main` in a downstream repo (e.g., `vig-os/devcontainer-smoke-test`)
2. `sync-main-to-dev.yml` triggers and creates PR targeting `dev`
3. Observe: no CI workflow runs appear for the sync branch/PR

### Expected Behavior

CI should trigger automatically via the `pull_request: opened` event, producing the required "CI Summary" check so the PR can merge (manually or via auto-merge).

### Actual Behavior

CI never runs. The only checks on the PR's head commit are from other workflows (dispatch, scorecard, sync) that ran on the same SHA in the context of `main`. The "CI Summary" check is missing, blocking the PR indefinitely.

Evidence from [vig-os/devcontainer-smoke-test#46](https://github.com/vig-os/devcontainer-smoke-test/pull/46):
- 0 workflow runs for `chore/sync-main-to-dev-9-1` branch
- 13 check runs present, none from CI
- Other PRs (e.g., deploy PRs) DO trigger CI normally

### Environment

- **Template**: `assets/workspace/.github/workflows/sync-main-to-dev.yml`
- **CI workflow**: `assets/workspace/.github/workflows/ci.yml`
- **Downstream repo**: `vig-os/devcontainer-smoke-test`
- **Downstream PR**: https://github.com/vig-os/devcontainer-smoke-test/pull/46

### Additional Context

Root cause hypothesis: the sync branch is created via the GitHub Refs API (`gh api repos/.../git/refs`), not via `git push`. API ref creation does not generate a `push` event. While `pull_request: opened` should still fire when the PR is created, GitHub may not trigger workflows in this scenario — possibly because the head commit already has runs from the `push` to `main`, or because of a GitHub limitation with API-created branches.

Deploy branches work because they use `git push`, generating proper push events before the PR is created.

### Possible Solution

Options to investigate:
1. **Switch to `git push`**: Replace the API branch creation (`gh api .../git/refs`) with `git checkout -b ... && git push` so the branch has a proper push event
2. **Post-PR push**: After creating the PR, push a no-op update to the sync branch to trigger `pull_request: synchronize`
3. **Explicit `workflow_dispatch`**: Trigger CI via `gh workflow run ci.yml --ref $SYNC_BRANCH` after PR creation (caveat: won't produce PR-associated checks)

### Changelog Category

Fixed

---
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
