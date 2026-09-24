---
type: issue
state: closed
created: 2026-09-23T14:02:42Z
updated: 2026-09-23T19:54:31Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1673
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-24T07:30:44.535Z
---

# [Issue 1673]: [Release 1.16.0-rc1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1673)


Release 1.16.0-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** build-and-test, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/35870438324)

**Release PR:** #1672

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.16.0-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 23, 2026 at 07:54 PM_

Resolved by the re-dispatch: 1.16.0 released and promoted (tag `1.16.0` at 1d42b88b, PR #1672 merged, GHCR `:latest` moved).

Not a content defect. `Build and Test (arm64)` failed on `test_ssh_github_authentication` — a live `ssh -T git@github.com` from inside the container on a 10-second timeout — with 41 passed / 1 failed; the amd64 lane was cancelled alongside it. The same test passed on PR #1672's CI over the identical tree, and the re-dispatch was green on both arches.

Rollback behaved exactly as designed: no tag was pushed, the release branch and draft PR were untouched, and the RC number was not burned (the retry published `1.16.0-rc1`, since cleaned up by promote).

