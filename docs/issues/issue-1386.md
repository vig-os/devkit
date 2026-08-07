---
type: issue
state: open
created: 2026-08-07T17:11:54Z
updated: 2026-08-07T17:14:55Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1386
comments: 1
labels: bug, area:ci
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:56.180Z
---

# [Issue 1386]: [Release 1.7.0-rc1 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1386)


Release 1.7.0-rc1 encountered an error during the automated release workflow.

**Failed Jobs:** vulnix-gate, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/31200317431)

**Release PR:** #1385

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.7.0-rc1-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 05:14 PM_

Root cause: the release-only Vulnix CVE Gate flagged **CVE-2026-66032** (CVSS 8.8, double-free in `sftp_open()`, libssh2 1.11.1) as unexcepted. It is the fourth member of the libssh2 malicious-server batch already excepted in `.vulnixignore` (CVE-2026-66033/66034/66035, block expires 2026-09-02, #1327/#1328) — it was not among the vulnix findings when that block was triaged on 2026-08-04 (published 2026-07-24; scored/ingested later), so it never got an entry.

Same closure provenance and reachability class as its siblings: libssh2 enters only as curl's scp/sftp backend; the flaw requires an authenticated SFTP session to a malicious SSH server.

Remediation lever today is still exception-only: upstream has published no libssh2 release; NixOS/nixpkgs#547491 (debian patches for CVE-2026-6603[2345]) merged to master 2026-08-07 12:41Z, but the 26.05 backport NixOS/nixpkgs#550166 targets staging-26.05 and is still open — the patched derivation has not reached the pinned nixos-26.05 channel.

Forward fix: add CVE-2026-66032 to the existing 2026-09-02 libssh2 block via a bugfix PR to `release/1.7.0`, then re-dispatch the candidate.

