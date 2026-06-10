---
type: issue
state: closed
created: 2026-06-10T08:57:37Z
updated: 2026-06-10T09:32:00Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/580
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-10T10:26:39.851Z
---

# [Issue 580]: [Release 0.3.5-rc1 failed -- automatic rollback](https://github.com/vig-os/devcontainer/issues/580)


Release 0.3.5-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** build-and-test, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devcontainer/actions/runs/27264595421)

**Release PR:** #575

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:0.3.5-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on June 10, 2026 at 09:31 AM_

Fixed in #581: targeted `libssl3`/`openssl` upgrade to `3.0.20-1~deb12u2` clears fixable HIGH CVE-2026-45447 that blocked the release Trivy gate. Re-run Release workflow as candidate (rc2) to validate.

