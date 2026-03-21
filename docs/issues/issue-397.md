---
type: issue
state: closed
created: 2026-03-20T11:02:20Z
updated: 2026-03-20T13:35:02Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/397
comments: 2
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:44.849Z
---

# [Issue 397]: [Smoke-test dispatch failed for 0.3.1-rc8](https://github.com/vig-os/devcontainer/issues/397)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc8`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23339409242`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23339409242
- source_sha: `a265a4db3ae9881f9da268916f22a2cb52b6c18d`
- correlation_id: `vig-os/devcontainer:23339409242:0.3.1-rc8`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23339858643
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/47
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `failure`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 20, 2026 at 01:12 PM_

## Root Cause Analysis

### Error

```
could not create workflow dispatch event: HTTP 403: Resource not accessible by integration
(https://api.github.com/repos/vig-os/devcontainer-smoke-test/actions/workflows/248843304/dispatches)
```

**Failing step:** `trigger-prepare-release` → step 5 "Trigger prepare-release" (`gh workflow run prepare-release.yml`)

### Root Cause

The `RELEASE_APP` GitHub App **lacks `actions:write` permission** on `devcontainer-smoke-test`.

The redesigned `repository-dispatch.yml` (PR #360, merged Mar 19) added `trigger-prepare-release` and `trigger-release` jobs that call `gh workflow run` to dispatch downstream workflows. The Actions API endpoint `POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches` requires `actions:write` on the calling token. The RELEASE_APP was only configured with `contents`, `issues`, and `pull_requests` read/write — `actions` was never included.

### Why was this not caught earlier?

| Run date | Run ID | Workflow version | Outcome |
|----------|--------|-----------------|---------|
| Mar 13 | `23072314370` | **Old** (3 jobs: Validate, Deploy, Summary) | **Success** — no workflow dispatch needed |
| Mar 17 | `23206472689` | Old (4 jobs) | Deploy/"Run installer" failed → `trigger-prepare-release` never existed |
| Mar 18 | `23234510565` | Old (4 jobs) | "Publish smoke-test release artifact" failed → same |
| **Mar 19** | `23304352254` | **New** (9 jobs, post-redesign) | Deploy path fixed → **first time `trigger-prepare-release` ran → HTTP 403** |
| Mar 20 ×3 | `23333150355` / `23335664018` / `23339858643` | New | Same 403 on `trigger-prepare-release` |

The redesign shipped new orchestration jobs that exercise a permission (`actions:write`) the App never had. Earlier failures at the Deploy stage masked this gap.

### Documented vs Required Permissions

`docs/RELEASE_CYCLE.md` documents RELEASE_APP with:

> Contents read/write, Issues read/write, Pull requests read/write

The new orchestration additionally requires: **Actions read/write** (for `gh workflow run` / workflow_dispatch API).

### Fix

1. **GitHub App configuration** (manual): Add `Actions: Read and write` to the RELEASE_APP installation on `vig-os/devcontainer-smoke-test`.
2. **Documentation**: Update `docs/RELEASE_CYCLE.md` to include the new `Actions read/write` permission requirement.
3. **Re-dispatch** `0.3.1-rc9` (or later) to validate the fix end-to-end.

---

# [Comment #2]() by [c-vigo]()

_Posted on March 20, 2026 at 01:35 PM_

Closing this as resolved.

A downstream re-dispatch using the latest RC reached a different failure point, which confirms the original `trigger-prepare-release` dispatch-permission problem from this issue is fixed.

Evidence run:
- https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23344856147/job/67908068340

Any new failure in that run should be tracked separately.

