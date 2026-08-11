---
type: issue
state: closed
created: 2026-08-07T18:14:43Z
updated: 2026-08-10T12:21:40Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devkit/issues/1390
comments: 2
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-11T03:50:29.910Z
---

# [Issue 1390]: [Release 1.7.0-rc2 failed -- automatic rollback](https://github.com/vig-os/devkit/issues/1390)


Release 1.7.0-rc2 encountered an error during the automated release workflow.

**Failed Jobs:** publish

**Workflow Run:** [View logs](https://github.com/vig-os/devkit/actions/runs/31204672354)

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
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:1.7.0-rc2-*` and remove any orphaned images manually.
- If a **draft** GitHub Release exists for this tag, edit or manage it from the Releases UI (**publishing** locks the linked tag and assets when **immutable releases** are enabled).

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Publish a new release candidate to validate the fix; re-run the final workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 10, 2026 at 11:38 AM_

Closing — transient infrastructure failure, superseded by the shipped 1.7.0 release.

**Root cause:** the `Publish Release` job failed only in the `Attest SBOM (retry)` step against the sigstore transparency log:

```
InternalError: error creating tlog entry
FetchError: network timeout at: https://rekor.sigstore.dev/api/v1/log/entries
```

Not a defect in the release workflow or the release content. Every other job in [run 31204672354](https://github.com/vig-os/devkit/actions/runs/31204672354) was green (Validate Release, Finalize Release, Build and Test amd64 + arm64, Vulnix CVE Gate), and the automatic rollback succeeded.

**Outcome:** the train continued past rc2 (rc3, rc5) and **1.7.0 was released and promoted on 2026-08-08** — tag `1.7.0` @ `88eea95496a188c730bddf97f839d5361d78a464`, GitHub release marked Latest.

**Manual cleanup items from the report — both verified clear:**
- No `1.7.0-rc*` image tags remain in GHCR; `ghcr.io/vig-os/devcontainer` carries only `1.7.0`, `1.7.0-amd64`, `1.7.0-arm64`, `latest` and prior releases.
- No release-candidate tags remain on the remote.

Nothing further to fix here. Attestation's sensitivity to Rekor availability (rc1 hit the same timeout) is a separate hardening concern and should be tracked in its own issue if we want it addressed.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 10, 2026 at 12:21 PM_

Follow-up filed as #1399 — widen the outer attestation backoff so the retry envelope survives a multi-minute Rekor incident (the action's internal retry gives ~47s per step; the current `sleep 30` outer layer brings the total to only ~2 minutes).

