---
type: issue
state: closed
created: 2026-03-20T13:30:34Z
updated: 2026-03-20T16:28:29Z
author: vig-os-release-app[bot]
author_url: https://github.com/vig-os-release-app[bot]
url: https://github.com/vig-os/devcontainer/issues/400
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:44.345Z
---

# [Issue 400]: [Smoke-test dispatch failed for 0.3.1-rc8](https://github.com/vig-os/devcontainer/issues/400)

Smoke-test dispatch failed while orchestrating downstream release validation.

## Dispatch metadata
- tag: `0.3.1-rc8`
- release_kind: `candidate`
- source_repo: `vig-os/devcontainer`
- source_workflow: `Release`
- source_run_id: `23339409242`
- source_run_url: https://github.com/vig-os/devcontainer/actions/runs/23339409242
- source_sha: `a265a4db3ae9881f9da268916f22a2cb52b6c18d`
- correlation_id: `manual:23339409242:0.3.1-rc8`

## Workflow context
- downstream workflow run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/23344856147
- deploy PR: https://github.com/vig-os/devcontainer-smoke-test/pull/48
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

_Posted on March 20, 2026 at 01:39 PM_

## Root Cause Analysis

### Summary

The `trigger-prepare-release` job failed because the downstream `prepare-release.yml` workflow in `devcontainer-smoke-test` attempted to commit the CHANGELOG freeze directly to the `dev` branch using `${{ github.token }}` (the default `GITHUB_TOKEN`), but the `dev` branch ruleset blocks direct pushes.

### Failure chain

```
repository-dispatch.yml (smoke-test)
  └─ trigger-prepare-release
       └─ dispatches → prepare-release.yml (smoke-test)
            └─ "Prepare Release Branch" job
                 └─ step 8: "Commit prepared CHANGELOG to dev via API"
                      └─ vig-os/commit-action → BLOCKED by ruleset
```

### Root cause

The smoke-test repo's `prepare-release.yml` (sourced from the workspace template at `assets/workspace/.github/workflows/prepare-release.yml`) uses `${{ github.token }}` for the `vig-os/commit-action` step:

```yaml
# workspace template (prepare-release.yml, line 202-204)
- name: Commit prepared CHANGELOG to dev via API
  uses: vig-os/commit-action@...
  env:
    GH_TOKEN: ${{ github.token }}     # ← default GITHUB_TOKEN
```

The `dev` branch has a "Dev protection" ruleset (ID `13444890`) requiring:
1. Changes made through a pull request
2. Required status check "CI Summary"

The only bypass actor is integration `2433383` (the Commit App). Since `GITHUB_TOKEN` is **not** the Commit App, the commit is rejected:

```
Repository rule violations found
Changes must be made through a pull request.
Required status check "CI Summary" is expected.
```

In contrast, the **devcontainer repo's own** `prepare-release.yml` correctly generates a Commit App Token and uses it:

```yaml
# devcontainer repo (prepare-release.yml, lines 157-163, 221-224)
- name: Generate Commit App Token
  id: commit-app-token
  uses: actions/create-github-app-token@...
  with:
    app-id: ${{ secrets.COMMIT_APP_ID }}
    private-key: ${{ secrets.COMMIT_APP_PRIVATE_KEY }}

- name: Commit prepared CHANGELOG to dev via API
  uses: vig-os/commit-action@...
  env:
    GH_TOKEN: ${{ steps.commit-app-token.outputs.token }}  # ← Commit App token (has bypass)
```

### Why it worked before / why it broke now

The "Dev protection" ruleset was likely added (or had its bypass actors misconfigured) after the workspace template was deployed to the smoke-test repo. The workspace template was never updated to use Commit App tokens, creating a drift between the devcontainer repo's own workflow and its template.

### State after failure

- Deploy PR #48 (`chore/deploy-0.3.1-rc8`): **merged successfully** — no cleanup needed
- CHANGELOG freeze commit: **not committed** (correctly blocked by ruleset)
- `release/0.3.1` branch: **not created** (step skipped after commit failure)
- Rollback handler: **ran cleanly** (nothing to undo)
- **No manual cleanup required**

### Fix

Update `assets/workspace/.github/workflows/prepare-release.yml` to match the devcontainer repo's approach:

1. Add a `Generate Commit App Token` step using `COMMIT_APP_ID` / `COMMIT_APP_PRIVATE_KEY` secrets
2. Replace all `GH_TOKEN: ${{ github.token }}` references in the `prepare` job with `GH_TOKEN: ${{ steps.commit-app-token.outputs.token }}`
3. Add a `Generate Release App Token` step for PR creation (matching devcontainer's pattern)
4. Redeploy the updated workflow to `devcontainer-smoke-test`
5. Re-dispatch with a new RC tag to verify

