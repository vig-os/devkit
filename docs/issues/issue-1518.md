---
type: issue
state: closed
created: 2026-08-14T15:32:34Z
updated: 2026-08-17T08:20:28Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1518
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:17.442Z
---

# [Issue 1518]: [Release 1.10.0-rc1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1518)


Release 1.10.0-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** validate, finalize, build-and-test, vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/31814853844)

**Release PR:** #1515

**Rollback Results:**
- Branch rollback: success
- PR body restoration: skipped

**Tag status (forward-fix policy):**
- Release tags are **not** deleted by automation (workflow choice; not the same as GitHub immutable-release lock-in).
- If the tag was pushed before the failure, it remains on the remote; use a new release candidate to validate fixes, then re-run the final release when ready.

**Actions Taken:**
- Release branch: this run's finalize commit(s) reverted, but only when the branch tip matched exactly what the run wrote — otherwise the branch is left untouched and the rollback result above is `failure` (#1462)
- Release PR body restored to TBD / prepare-release format when applicable (best-effort)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.10.0-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 08:20 AM_

Root cause of the rc1 failure was #1516 (agent-fingerprint check blocking the release PR plus the validate gate counting superseded FAILURE runs), closed 2026-08-14; 1.10.0 shipped and was promoted the same day. The two remaining remediations are tracked in #1521 (fingerprint context guard for emails) and #1522 (latest-per-name check-run dedup in the CI-green gate), both on milestone 1.11.0. No manual cleanup was needed: the rollback succeeded and no orphaned rc1 images or draft releases remain. Closing as resolved.

