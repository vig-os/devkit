---
type: issue
state: open
created: 2026-06-22T11:41:45Z
updated: 2026-06-22T11:41:45Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/616
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-22T20:15:51.479Z
---

# [Issue 616]: [Release 0.3.8-rc1 failed -- automatic rollback](https://github.com/vig-os/devcontainer/issues/616)


Release 0.3.8-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** validate, finalize, build-and-test, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devcontainer/actions/runs/27950027799)

**Release PR:** #null

**Rollback Results:**
- Branch rollback: success
- PR body restoration: skipped

**Tag status (forward-fix policy):**
- Release tags are **not** deleted by automation (workflow choice; not the same as GitHub immutable-release lock-in).
- If the tag was pushed before the failure, it remains on the remote; use a new release candidate to validate fixes, then re-run the final release when ready.

**Actions Taken:**
- Release branch reset to pre-finalization state (best-effort)
- Release PR body restored to TBD / prepare-release format when applicable (best-effort)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:0.3.8-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

