---
type: issue
state: closed
created: 2026-08-12T11:34:15Z
updated: 2026-08-12T13:15:44Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devkit/issues/1465
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:35.058Z
---

# [Issue 1465]: [Smoke-test dispatch failed for 1.8.0-rc3](https://github.com/vig-os/devkit/issues/1465)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `1.8.0-rc3`
- release_kind: `candidate`
- source_repo: `vig-os/devkit`
- source_workflow: `Release`
- source_run_id: `31590939254`
- source_run_url: https://github.com/vig-os/devkit/actions/runs/31590939254
- source_sha: `4c6d57dc5329d4c19bd2cbd39718280aa8591bed`
- correlation_id: `vig-os/devkit:31590939254:1.8.0-rc3`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31592199981
- deploy PR: https://github.com/vig-os/devkit-smoke-test/pull/359
- release PR: not created

## Job results
- validate: `success`
- deploy: `success`
- wait-deploy-merge: `failure`
- cleanup-release: `skipped`
- trigger-prepare-release: `skipped`
- ready-release-pr: `skipped`
- trigger-release: `skipped`
- wait-release-pr-ci: `skipped`
- trigger-promote-release: `skipped`
- summary: `failure`

## Manual cleanup guidance
- Inspect deploy/release PRs and workflow logs before retrying.
- If needed, close stale release PRs and delete stale `release/<version>` branch.
- Do not rewrite or delete **published** GitHub Releases (or their linked tags when **immutable releases** are enabled) to retry the same version; bare git tags without a published release are not locked by that feature unless a tag ruleset applies.
- After fixing the root cause upstream, publish a **new** RC tag (or a new final attempt only after branch/tag state matches your release policy), then rely on a fresh dispatch.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 01:15 PM_

Resolved. Root-caused as #1466: smoke mode was the only copy branch carrying `rsync --delete`, so the deploy removed every tracked path the template does not ship — the smoke repo's own `pyproject.toml`, `uv.lock`, `src/` and `tests/`. With no `pyproject.toml` on the branch, the drift gate's normal-mode re-scaffold stopped detecting a Python repo and re-rendered CodeQL and `.gitignore` language-neutral, so `Scaffold Drift` failed and `Wait for deploy PR merge` aborted the chain.

Fixed in #1468 (merged `eaa2fb9b`) and live-proven at 1.8.0-rc4: deploy PR devkit-smoke-test#360 deleted only the two retired workflows, kept the Python project, cleared the drift gate and auto-merged. The full chain ran green through release PR + CI, with promote correctly skipped for a candidate.

