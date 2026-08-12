---
type: issue
state: closed
created: 2026-08-12T09:59:24Z
updated: 2026-08-12T10:01:34Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1458
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:36.589Z
---

# [Issue 1458]: [Release 1.8.0-rc2 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1458)


Release 1.8.0-rc2 encountered an error during the automated release workflow.

**Failed Jobs:** publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/31583273344)

**Release PR:** #1441

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.8.0-rc2-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 10:01 AM_

Expected failure, already diagnosed: this was the re-run of rc2's Publish job hitting the candidate-mode concurrency guard (`Candidate tag '1.8.0-rc2' already exists on origin`) — the retry tolerance for existing tags applies only to final releases. Recovery agreed with the maintainer: delete the unpublished rc2 tag (no GitHub Release object is linked, so no tombstone risk — promote cleanup deletes exactly this class of tag anyway) and re-run the failed job again to complete 1.8.0-rc2 from its validated artifacts.

