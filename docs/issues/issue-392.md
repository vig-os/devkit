---
type: issue
state: closed
created: 2026-03-20T08:56:39Z
updated: 2026-03-20T10:19:40Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/392
comments: 2
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:45.810Z
---

# [Issue 392]: [Smoke-test dispatch failed for 0.3.1-rc7](https://github.com/vig-os/devcontainer/issues/392)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc7`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23335234319`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23335234319
- source_sha: `a154152c003fe84570759796c6f21d1f7cae6aae`
- correlation_id: `vig-os/devcontainer:23335234319:0.3.1-rc7`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23335664018
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/44
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

_Posted on March 20, 2026 at 09:02 AM_

## Root Cause Analysis

**Downstream run:** https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23335664018  
**Failing job:** *Trigger and wait for prepare-release workflow*  
**Failing step:** *Preflight check required release workflows on dispatch ref*

### What happened

Orchestration failed **before** `prepare-release` was triggered or waited on. Validate → deploy → wait for deploy PR merge → cleanup all succeeded; `ready-release-pr` and `trigger-release` were skipped as downstream dependencies.

### Root cause

Preflight runs `gh workflow view prepare-release.yml --ref dev` (and the same for `release.yml`). The runner's `gh` exits with:

`--yaml required when specifying --ref`

So the check is **invalid for the current GitHub CLI**: with `--ref`, `workflow view` now requires `--yaml`. This is a **preflight / CLI invocation** failure, not evidence that `prepare-release.yml` is missing on `dev`, and not a failed `prepare-release` workflow conclusion (no such run was started from this path).

### Note on log wording

Because the error text does not match `404|not found`, the script reports the generic "non-contract" (auth/API/network) path; that branch does not apply here—the failure is deterministic CLI usage.

---

# [Comment #2]() by [c-vigo]()

_Posted on March 20, 2026 at 09:03 AM_

## Implementation Plan

### Context

- **Source of truth:** `vig-os/devcontainer` — the smoke-test dispatch workflow is maintained here under `assets/smoke-test/.github/workflows/repository-dispatch.yml` and deployed into **`vig-os/devcontainer-smoke-test`** as the validation/test harness. Fixing the bug belongs in **this repo**; the downstream repo only receives the updated template via the normal smoke-test deploy path.
- **Goal:** Restore the **Preflight check required release workflows on dispatch ref** step so it succeeds on current GitHub CLI (`gh workflow view` with `--ref` requires `--yaml`), unblocking `trigger-prepare-release` and the rest of downstream orchestration after the next deploy.

### Changes (this repo)

1. **`assets/smoke-test/.github/workflows/repository-dispatch.yml`** — In the preflight step, invoke workflows at `WORKFLOW_REF` with YAML output, e.g.  
   `gh workflow view "${workflow_file}" --ref "${WORKFLOW_REF}" --yaml >/dev/null`  
   (preserve exit-status semantics and the existing loop over `prepare-release.yml` / `release.yml`).
2. **Optional:** Tighten error classification when `gh` fails so “`--yaml` required when specifying `--ref`” is not lumped under the generic auth/API/network path.
3. **`tests/bats/just.bats`** — Update the regression `grep` that pins the preflight snippet so it matches the new `gh` invocation (see the assertion around `WORKFLOW_CHECK_OUTPUT` / `gh workflow view`).

### Verification

- `bats tests/bats/just.bats` (or the project’s usual subset) passes.
- After merge and **smoke-test repo** picks up the new workflow (per existing deploy/promotion process), re-run or dispatch **smoke-test-trigger** and confirm preflight succeeds and `prepare-release` is actually triggered when intended.

### Commit / traceability

- **Refs:** #392

### Out of scope

- Editing workflow YAML only in `devcontainer-smoke-test` without updating `assets/smoke-test/` here (would diverge from SSoT).

