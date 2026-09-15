---
type: issue
state: closed
created: 2026-09-14T08:29:33Z
updated: 2026-09-14T09:50:21Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1622
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-15T07:34:14.053Z
---

# [Issue 1622]: [Release 1.14.1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1622)


Release 1.14.1 encountered an error during the automated release workflow.

**Failed Jobs:** validate, finalize, build-and-test, vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/34822833899)

**Release PR:** #1620

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.14.1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 14, 2026 at 09:50 AM_

Root cause: the final dispatch ran while PR #1620 was still a **draft** — `validate` failed on the draft gate before any mutation (no finalize commit, no tag, no GHCR push came from run 34822833899; the downstream jobs in the list failed only as dependents). Remedied by `gh pr ready 1620` and re-dispatching: run [34823019353](https://github.com/vig-os/devkit/actions/runs/34823019353) succeeded, and 1.14.1 was promoted the same morning (#1620 merged, release published). Rollback was a clean no-op; no manual cleanup needed — the live `1.14.1` tag/images are the successful retry's.

