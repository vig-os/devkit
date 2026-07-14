---
type: issue
state: closed
created: 2026-07-13T13:27:32Z
updated: 2026-07-13T16:18:01Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1020
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T04:57:27.936Z
---

# [Issue 1020]: [Release 1.1.0-rc2 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1020)


Release 1.1.0-rc2 encountered an error during the automated release workflow.

**Failed Jobs:** build-and-test, vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/29253223587)

**Release PR:** #1014

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.1.0-rc2-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 04:18 PM_

Closing as a transient infrastructure failure — no code defect, and no PR to attribute.

Both failing jobs (`Vulnix CVE Gate`, `Build and Test (arm64)`) died during **Set up job**, before any devkit code ran:

```
Failed to resolve action download info. Error: Service Unavailable
Retrying in 13.751 seconds
Failed to resolve action download info. Error: Service Unavailable
Retrying in 25.47 seconds
##[error]Service Unavailable
##[error]Failed to resolve action download info.
```

That is a GitHub Actions service outage resolving action downloads, not a rollback-worthy regression. `build-and-test (amd64)`, `publish` and the smoke-test dispatch were merely *cancelled* as a consequence. rc3 and the final [1.1.0](https://github.com/vig-os/devkit/releases/tag/1.1.0) release ran green on the same code, confirming it. No manual cleanup was needed.

