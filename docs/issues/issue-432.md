---
type: issue
state: closed
created: 2026-03-24T16:28:40Z
updated: 2026-03-25T09:09:04Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/432
comments: 2
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:36.217Z
---

# [Issue 432]: [Smoke-test dispatch failed for 0.3.1-rc18](https://github.com/vig-os/devcontainer/issues/432)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc18`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23499741825`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23499741825
- source_sha: `27b128975c1a7591e658796ba8ca023e9dd156cb`
- correlation_id: `vig-os/devcontainer:23499741825:0.3.1-rc18`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23500334272
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/84
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/85

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `failure`
- trigger-release: `skipped`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 25, 2026 at 06:48 AM_

## Root cause analysis

### What failed
The downstream run failed in job **`ready-release-pr`** ("Prepare release PR") on step **Approve release PR for automated dispatch** — [job log](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23500334272/job/68394016524). Earlier jobs (`validate`, `deploy`, `wait-deploy-merge`, `cleanup-release`, `trigger-prepare-release`) succeeded; `trigger-release` and `merge-release-pr` were skipped because this job failed.

### Why
That step runs `gh pr review --approve` using the default `GITHUB_TOKEN` (`github.token`). GitHub does not allow that token to approve pull requests unless the repository (or organization) has **Allow GitHub Actions to create and approve pull requests** enabled under Actions workflow permissions.

Other steps in the same job use the Release App token for PR discovery/edits; only the approve step uses `github.token`, which matches "everything worked until approve."

### Culprit
Configuration/policy on **`vig-os/devcontainer-smoke-test`**: the setting above is off (or not inherited), so automated approval is rejected and the step exits 1.

### Not the cause
- RC tag / dispatch payload / upstream `vig-os/devcontainer` publish path — dispatch and prior downstream steps completed successfully.

### Fix options
1. **Repo/org setting:** Enable *Allow GitHub Actions to create and approve pull requests* for the smoke-test repo (or org).
2. **Workflow change:** Approve with a token that branch protection allows (e.g. redesign the step in `assets/smoke-test/.github/workflows/repository-dispatch.yml` and redeploy the template to the smoke-test repo), if you prefer not to enable that setting.

Template reference: `assets/smoke-test/.github/workflows/repository-dispatch.yml` (`ready-release-pr` → Approve release PR for automated dispatch).

---

# [Comment #2]() by [c-vigo]()

_Posted on March 25, 2026 at 09:09 AM_

> * **Repo/org setting:** Enable _Allow GitHub Actions to create and approve pull requests_ for the smoke-test repo (or org).

implemented this.

