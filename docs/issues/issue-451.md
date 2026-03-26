---
type: issue
state: closed
created: 2026-03-26T12:54:19Z
updated: 2026-03-26T15:11:47Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/451
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:30.916Z
---

# [Issue 451]: [Smoke-test dispatch failed for 0.3.1-rc24](https://github.com/vig-os/devcontainer/issues/451)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc24`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23594310918`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23594310918
- source_sha: `6f790039c606880a23e4d7ed639afa5254329234`
- correlation_id: `vig-os/devcontainer:23594310918:0.3.1-rc24`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23595002617
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/104
- release PR: https://github.com/vig-os/devcontainer-smoke-test/pull/105

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
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
---

# [Comment #1]() by [c-vigo]()

_Posted on March 26, 2026 at 02:42 PM_

## RCA: Smoke-test dispatch failed for `0.3.1-rc24`

### Summary

The downstream **Release** workflow on `vig-os/devcontainer-smoke-test` failed during the **Publish Release** phase. The smoke-test orchestration job **Trigger and wait for release workflow** correctly reported `failure` because the parent run concluded with `conclusion: failure`.

### Root cause

The workspace orchestrator [`assets/workspace/.github/workflows/release.yml`](https://github.com/vig-os/devcontainer/blob/main/assets/workspace/.github/workflows/release.yml) passes `tag_already_exists` into the reusable workflow [`release-publish.yml`](https://github.com/vig-os/devcontainer/blob/main/assets/workspace/.github/workflows/release-publish.yml) as:

```yaml
tag_already_exists: ${{ needs.core.outputs.tag_already_exists }}
```

`needs.core.outputs.tag_already_exists` is always a **string** (`"true"` or `"false"`) because job outputs from shell steps are strings. The called workflow declares that input as **`type: boolean`**. GitHub Actions rejects the `workflow_call` when the value is not a proper boolean, so the **Publish Release** job fails **before any sub-jobs appear** in the UI/API.

The monolithic [`.github/workflows/release.yml`](https://github.com/vig-os/devcontainer/blob/main/.github/workflows/release.yml) in this repo avoids the problem by comparing the output as a string (e.g. `!= 'true'`) instead of passing it into a boolean-typed reusable input.

### Failure chain

1. Upstream publishes `0.3.1-rc24` and dispatches `repository_dispatch` to the smoke-test repo.
2. Deploy merges updated workspace workflows (including commit `1bb5f78` — idempotent tags / `tag_already_exists` wiring).
3. `trigger-release` runs `gh workflow run release.yml` on `dev` with `version=0.3.1`, `release-kind=candidate`, `rc-number=24`.
4. **Release Core** and **Release Extension** succeed; **Finalize** logs show `No remote tag 0.3.1-rc24 yet` and sets `tag_already_exists=false` (string).
5. **Publish Release** reusable call fails at input validation → overall run `failure` → **Rollback on Failure** runs (e.g. [devcontainer-smoke-test#106](https://github.com/vig-os/devcontainer-smoke-test/issues/106)).

### Evidence

| Item | Detail |
|------|--------|
| Orchestration run | [23595002617](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23595002617) — `trigger-release` ended with `ERROR: release workflow concluded with 'failure'` |
| Downstream Release run | [23595160097](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23595160097) — no `Publish Release / *` jobs; rollback ran |
| Last good RC on same repo | [23549773061](https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23549773061) (`0.3.1-rc23`) — **had** `Publish Release` sub-jobs |
| Workflow diff | `release.yml` gained `tag_already_exists: ${{ needs.core.outputs.tag_already_exists }}`; `release-publish.yml` gained `type: boolean` input |


