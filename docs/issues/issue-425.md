---
type: issue
state: closed
created: 2026-03-24T07:33:08Z
updated: 2026-03-24T08:24:21Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/425
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T04:26:17.955Z
---

# [Issue 425]: [Smoke-test dispatch failed for 0.3.1-rc15](https://github.com/vig-os/devcontainer/issues/425)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc15`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23477514466`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23477514466
- source_sha: `dc28eb362bd94aa9b0c56954cbb07c956c920dd1`
- correlation_id: `vig-os/devcontainer:23477514466:0.3.1-rc15`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23477971963
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/76
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/77

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `success`
- cleanup-release: `success`
- trigger-prepare-release: `success`
- ready-release-pr: `success`
- trigger-release: `failure`
- merge-release-pr: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Re-dispatch using a new RC tag/version once root cause is fixed.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 24, 2026 at 08:08 AM_

## RCA: `trigger-release` / Release Core validate failure (job 68315258492)

**Failing step:** Release Core → **Validate Release Core** → **Find and verify PR**  
**Symptom:** Process exited with **127** — consistent with **`jq: command not found`** when the shell tries to run the standalone `jq` binary.

### Root cause

- Reusable workflow **`release-core.yml`** runs the **validate** job in container **`ghcr.io/vig-os/devcontainer:<tag>`** (see `jobs.validate.container.image`).
- Step **Find and verify PR** pipes `gh pr list` JSON into **`jq`** (`echo "$PR_JSON" | jq …`, and similar for `STATUS_ROLLUP`).
- The devcontainer **`Containerfile`** installs many CLI tools via `apt-get` but **does not install the `jq` package**. GitHub’s **`ubuntu-*` runners** typically include `jq`, so this only breaks when the job runs **inside our image**, not when comparing to a bare Ubuntu job.

**Not the same:** `gh … --jq '…'` uses **GitHub CLI’s** built-in JSON query support and does **not** require the system `jq` package. This failure is specifically **invoking `jq` as a separate command**.

### Scan: other containerized workspace workflows

Audited `assets/workspace/.github/workflows/*` jobs that use **`container: ghcr.io/vig-os/devcontainer:…`** for **standalone `jq`** (`| jq` / `jq '…'` outside `gh --jq`):

- **Only match:** `release-core.yml` — **Validate Release Core** / **Find and verify PR** (the failing pattern).
- **No other** container jobs in that tree use pipe-to-`jq`; they use **`gh`**, **`git`**, **`retry`** (vig-utils), **`just`**, **`prepare-changelog`**, **`awk`**, **`python3`**, etc., which align with what the image already provides.

**Smoke-test** `repository-dispatch.yml` jobs use **`runs-on: ubuntu-22.04`** only and **`gh --jq`**, so they are not affected by missing system `jq` in the devcontainer image.

### Remediation options

1. **Image:** add **`jq`** to the devcontainer **`Containerfile`** `apt-get install` list (minimal change to workflow logic).  
2. **Workflow:** refactor **Find and verify PR** to avoid external `jq` (e.g. express checks via **`gh` `--jq`** only, or use Python already in the image).

Refs: failing job https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23478133458/job/68315258492

