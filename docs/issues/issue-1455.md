---
type: issue
state: closed
created: 2026-08-12T09:49:03Z
updated: 2026-08-12T09:51:13Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1455
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:38.424Z
---

# [Issue 1455]: [Release 1.8.0-rc2 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1455)


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

_Posted on August 12, 2026 at 09:51 AM_

Transient sigstore infrastructure failure, not a release defect: the SBOM attestation timed out against rekor.sigstore.dev (`FetchError: network timeout at https://rekor.sigstore.dev/api/v1/log/entries`), after all validate/build/test jobs were green. Same signature as the 1.7.0 train's rc1/rc2 transients. Forward-fix per policy: rc2's tag is burned, 1.8.0-rc3 dispatched (run 31584765199).

