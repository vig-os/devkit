---
type: issue
state: closed
created: 2026-07-23T12:58:29Z
updated: 2026-07-23T15:05:17Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1261
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-23T15:08:26.145Z
---

# [Issue 1261]: [Release 1.4.1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1261)


Release 1.4.1 encountered an error during the automated release workflow.

**Failed Jobs:** validate, finalize, build-and-test, vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/30009077181)

**Release PR:** #1247

**Rollback Results:**
- Branch rollback: success
- PR body restoration: success

**Tag status (forward-fix policy):**
- Release tags are **not** deleted by automation (workflow choice; not the same as GitHub immutable-release lock-in).
- If the tag was pushed before the failure, it remains on the remote; use a new release candidate to validate fixes, then re-run the final release when ready.

**Actions Taken:**
- Release branch reset to pre-finalization state (best-effort)
- Release PR body restored to TBD / prepare-release format when applicable (best-effort)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.4.1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 03:05 PM_

Root cause: the final-mode `Validate Release` gate found PR #1247 with `reviewDecision: REVIEW_REQUIRED` — the finalize was dispatched before the maintainer approval landed (same gate as the 1.4.0 first-attempt failure). No mutation occurred: validation aborted before tagging/publishing, so the rollback job had nothing to undo. PR #1247 is now APPROVED; re-dispatching `release.yml` (final) for 1.4.1.

