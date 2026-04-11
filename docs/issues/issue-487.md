---
type: issue
state: closed
created: 2026-04-05T18:35:25Z
updated: 2026-04-07T08:00:01Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/487
comments: 1
labels: bug, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-11T04:27:32.076Z
---

# [Issue 487]: [Release 0.3.2 failed -- automatic rollback](https://github.com/vig-os/devcontainer/issues/487)


Release 0.3.2 encountered an error during the automated release workflow.

**Failed Jobs:** finalize, build-and-test, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devcontainer/actions/runs/24007826951)

**Release PR:** #486

**Rollback Results:**
- Branch rollback: success

**Tag status (forward-fix policy):**
- Release tags are **not** deleted by automation (workflow choice; not the same as GitHub immutable-release lock-in).
- If the tag was pushed before the failure, it remains on the remote; use a new release candidate to validate fixes, then re-run the final release when ready.

**Actions Taken:**
- Release branch reset to pre-finalization state (best-effort)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:0.3.2-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on April 7, 2026 at 06:51 AM_

## Root Cause Analysis

### Summary

The `finalize` job failed because the "Release protection" ruleset (ID `14268611`) blocked the `vig-os/commit-action` from pushing the finalization commit directly to `release/0.3.2`.

### Failed Step

**"Commit finalization changes via API"** in the `finalize` job. The API returned:

> Repository rule violations found
> - Changes must be made through a pull request.
> - Required status check "Test Summary" is expected.

### Direct Cause

The `vig-os/commit-action@v0.2.0` pushes commits by calling [`PATCH /repos/{owner}/{repo}/git/refs/{ref}`](https://docs.github.com/rest/git/refs#update-a-reference). The "Release protection" ruleset enforces two rules on `refs/heads/release/*`:

| Rule | Effect |
|------|--------|
| `pull_request` | Requires changes via PR (blocks direct ref updates) |
| `required_status_checks` | Requires "Test Summary" to pass |

The ruleset grants bypass to **one** actor:

| Actor | Type | App ID |
|-------|------|--------|
| `commit-action-bot` | Integration | 2433383 |

However, the finalize job authenticates with a token from **`vig-os-release-app`** (app ID 2930017), generated via `actions/create-github-app-token` using `RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY`. This token is passed to `commit-action` as `GH_TOKEN`. Since `vig-os-release-app` is **not** in the bypass list, the API rejects the ref update.

### Triggering Event

The "Release protection" ruleset was **updated on 2026-04-05 at 11:26 UTC** — approximately 7 hours before the failed final release (18:34 UTC). The 0.3.1 final release on March 26 used the identical workflow and commit-action version (`v0.2.0`) with the same `GH_TOKEN` source, and succeeded. This confirms the April 5 ruleset update introduced the blocking condition.

### Why It Wasn't Caught Earlier

- The **RC run** (same day, 11:38 UTC — 12 minutes after the ruleset update) succeeded because `release-kind=candidate` **skips** the entire finalize-commit path (no changelog date set, no commit-action invocation).
- No other mechanism exercises direct pushes to `release/*` branches between RC and final.

### Cascade

```
finalize FAILED
  → build-and-test SKIPPED (depends on finalize)
  → publish SKIPPED (depends on build-and-test)
  → smoke-test SKIPPED (depends on publish)
  → rollback SUCCEEDED (reset release/0.3.2 to pre-finalize SHA)
```

No tag was pushed, no images were published to GHCR, no GitHub Release draft was created.

### Timeline

| Time (UTC) | Event |
|------------|-------|
| Mar 24 | "Release protection" ruleset created |
| Mar 26 17:52 | 0.3.1 final release — `commit-action` finalize **succeeded** |
| Apr 05 11:26 | "Release protection" ruleset **updated** |
| Apr 05 11:38 | 0.3.2 RC — succeeded (skips finalize-commit path) |
| Apr 05 18:34 | 0.3.2 final — `commit-action` finalize **failed** |
| Apr 05 18:35 | Rollback job — branch reset succeeded, this issue created |


