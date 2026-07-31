---
type: issue
state: closed
created: 2026-07-30T09:48:56Z
updated: 2026-07-30T22:00:17Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1303
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-31T05:42:06.798Z
---

# [Issue 1303]: [Release 1.5.0-rc1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1303)


Release 1.5.0-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/30531160197)

**Release PR:** #1301

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.5.0-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 30, 2026 at 10:00 PM_

rc1's Publish failure was a transient GitHub release-asset CDN blip in the syft installer (masked-redirect signature; same environment green on 1.4.2 and on every subsequent candidate). Superseded by rc2–rc4 and the 1.5.1 final — RELEASED+PROMOTED 2026-07-30.

