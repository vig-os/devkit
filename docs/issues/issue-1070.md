---
type: issue
state: closed
created: 2026-07-14T15:56:12Z
updated: 2026-07-14T21:22:05Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1070
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:35.024Z
---

# [Issue 1070]: [Release 1.2.0-rc1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1070)


Release 1.2.0-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/29346662524)

**Release PR:** #1068

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.2.0-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:22 PM_

Root cause: the Vulnix CVE Gate correctly blocked on four fresh gawk 5.4.0 findings (CVE-2026-40467/-40468/-40469/-40553, CERT-PL disclosure of 2026-07-13) — a genuine new-CVE gate trip, not a pipeline defect. Triaged in #1071 and excepted with a short-dated register block via PR #1072 (expiry 2026-07-28, pending the nixpkgs gawk 5.4.1 bump reaching nixos-26.05).

Cleanup verification: the rollback left the release branch clean (no reset needed — the failure preceded finalization changes); no tag was pushed by the failed run, and no orphaned `1.2.0-rc1-*` GHCR images resulted (publish never ran).

Resolution: after the exception merged, [1.2.0-rc1](https://github.com/vig-os/devkit/actions/runs/29358221596) published green (vulnix gate passing) and **[1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) is released and promoted**.

