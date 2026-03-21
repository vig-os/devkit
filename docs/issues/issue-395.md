---
type: issue
state: closed
created: 2026-03-20T09:30:09Z
updated: 2026-03-20T10:44:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/395
comments: 1
labels: bug, area:ci, area:workflow, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:45.196Z
---

# [Issue 395]: [[BUG] sync-main-to-dev fails in container jobs because run steps use sh instead of bash](https://github.com/vig-os/devcontainer/issues/395)

## Description
The downstream smoke-test run for `Sync main to dev` fails before branch comparison logic executes because containerized `run:` steps are executed with `sh`, but the workflow scripts use `set -euo pipefail`.

## Steps to Reproduce
1. Trigger downstream smoke-test dispatch that runs `assets/workspace/.github/workflows/sync-main-to-dev.yml`.
2. Open the `Check if dev is up to date` job.
3. Inspect step `Check if dev is up to date with main`.
4. Observe shell startup and immediate script failure.

## Expected Behavior
The `check` and `sync` jobs execute shell scripts successfully in container jobs, including `set -euo pipefail`, and continue to branch comparison / PR sync logic.

## Actual Behavior
The script fails immediately with:
`set: Illegal option -o pipefail`
because the container job uses `shell: sh -e {0}` by default.

## Environment
- **OS**: GitHub Actions `ubuntu-22.04`
- **Container Runtime**: Docker (GitHub-hosted runner)
- **Image Version/Tag**: `ghcr.io/vig-os/devcontainer:0.3.0-rc2`
- **Architecture**: AMD64
- **Workflow run**: [Run 23335537572, job 67876302991](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23335537572/job/67876302991)

## Additional Context
- Upstream non-container workflow does not exhibit this because default shell is bash on VM jobs.
- Workspace template version runs `check`/`sync` in containers, which changes default shell behavior.

## Possible Solution
- Add job defaults to force bash in containerized jobs:
  - `assets/workspace/.github/workflows/sync-main-to-dev.yml`
  - Jobs: `check`, `sync`
  - Add:
    ```yaml
    defaults:
      run:
        shell: bash
    ```
- Keep `set -euo pipefail` unchanged.
- Related to #394 (downstream workflow hardening).

## Changelog Category
Fixed

## Acceptance Criteria
- [ ] `check` and `sync` jobs in `sync-main-to-dev.yml` explicitly run `run:` steps with bash.
- [ ] Smoke-test downstream run no longer fails on `set -euo pipefail`.
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
---

# [Comment #1]() by [c-vigo]()

_Posted on March 20, 2026 at 10:44 AM_

Successful downstream run [23339310830](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23339310830), opened [PR#46](https://github.com/vig-os/devcontainer-smoke-test/pull/46)

