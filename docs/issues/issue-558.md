---
type: issue
state: closed
created: 2026-06-08T13:19:01Z
updated: 2026-06-08T14:23:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/558
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-09T06:16:00.434Z
---

# [Issue 558]: [[BUG] Renovate changelog workflow step runs under dash, failing on 'set -o pipefail'](https://github.com/vig-os/devcontainer/issues/558)

## Description

The "Update CHANGELOG.md from Renovate PR metadata" step in `.github/workflows/renovate-changelog.yml` declares `shell: bash` and runs `set -euo pipefail`, but inside the resolved container image it executes under `sh`/dash. dash rejects `set -o pipefail`, so the step exits with code 2 before `renovate-changelog-pr` ever runs. This fails the `changelog` check on every Renovate PR (#553-556).

## Steps to Reproduce

1. Renovate opens/synchronizes a PR.
2. The `Renovate changelog` workflow runs the `changelog` job in container `ghcr.io/vig-os/devcontainer:<tag>`.
3. The step runs `set -euo pipefail`.
4. The script aborts.

## Expected Behavior

The step runs under bash; `renovate-changelog-pr` executes and appends the Unreleased changelog entry.

## Actual Behavior

```
/__w/_temp/....sh: 1: set: Illegal option -o pipefail
##[error]Process completed with exit code 2.
```

## Environment

- **OS**: CI (Ubuntu 24.04 host)
- **Container Runtime**: container job `ghcr.io/vig-os/devcontainer:dev`
- **Image Version/Tag**: `dev`
- **Architecture**: AMD64

## Additional Context

Failing on PRs #553-556 ([example job](https://github.com/vig-os/devcontainer/actions/runs/27139267171/job/80099795213)). The job runs inside the devcontainer image, so `shell: bash` is unexpectedly resolving to dash (bash likely not the default/`/bin/sh`, or not on the expected PATH in the container).

Acceptance criteria:

- [ ] `changelog` step executes under bash and runs `renovate-changelog-pr` successfully on Renovate PRs
- [ ] Root cause of bash to dash fallback identified and fixed (not just worked around)
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Possible Solution

Investigate why `shell: bash` resolves to dash in the container step (ensure bash is present and the default, or set an explicit bash path). Alternatively make the script POSIX-compliant by removing the `pipefail` bashism.

**Changelog Category**: Fixed
---

# [Comment #1]() by [c-vigo]()

_Posted on June 8, 2026 at 02:23 PM_

Closing as a duplicate of #550.

The fix is already on `dev`: commit `61aacce` ("fix(ci): unblock Renovate PR CI gates", under #550) added `shell: bash` to the "Update CHANGELOG.md from Renovate PR metadata" step, so `set -euo pipefail` runs under bash inside the container.

Root cause confirmed: `renovate-changelog.yml` runs via `pull_request_target`, which always reads the workflow definition from the default branch (`main`). `main` does not yet have the `shell: bash` line, so the step falls back to the container default `sh -e {0}` (dash) and aborts on `set -o pipefail`. `dev` already has the fix.

No further code change is required — the failures stop once `dev` is merged into `main` at the next release. Tracking the merge under #550.

