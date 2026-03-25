---
type: issue
state: closed
created: 2026-03-25T07:01:08Z
updated: 2026-03-25T09:07:58Z
author: github-actions[bot]
author_url: https://github.com/github-actions[bot]
url: https://github.com/vig-os/devcontainer/issues/434
comments: 1
labels: bug, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-25T17:01:35.297Z
---

# [Issue 434]: [Release 0.3.1-rc19 failed -- automatic rollback](https://github.com/vig-os/devcontainer/issues/434)


Release 0.3.1-rc19 encountered an error during the automated release workflow.

**Failed Jobs:** build-and-test, publish

**Workflow Run:** [View logs](https://github.com/vig-os/devcontainer/actions/runs/23528803329)

**Release PR:** #342

**Rollback Results:**
- Branch rollback: success
- Tag deletion: success

**Actions Taken:**
- Release branch rolled back to pre-finalization state
- Release tag deleted (if created)
- This issue created for investigation

**Manual Cleanup May Be Needed:**
- If images were pushed to GHCR before the failure, they are **not** automatically deleted. Check `ghcr.io/vig-os/devcontainer:0.3.1-rc19-*` and remove any orphaned images manually.

**Next Steps:**
1. Review the workflow logs to identify the root cause
2. Check rollback results above; fix any partial rollback manually
3. Fix the issue on the release branch
4. Re-run the workflow when ready

For details, check the workflow run linked above.

---

# [Comment #1]() by [c-vigo]()

_Posted on March 25, 2026 at 07:50 AM_

## Root cause analysis (local repro)

**Symptom:** `build-and-test` / image build fails during the Containerfile `RUN` that installs Cursor Agent.

**Repro (local):** Full `podman build` (or equivalent) reaches **STEP 32/57** and exits non-zero.

**Failure chain**

1. The Dockerfile runs `curl -fsSL https://cursor.com/install | bash` then `agent --version`.
2. The installer detects `linux/x64` and tries to download the agent package from a versioned URL under `downloads.cursor.com` (in this repro: `.../lab/2026.03.24-933d5a6/linux/x64/agent-cli-package.tar.gz`).
3. **`curl` gets HTTP 403** on that artifact URL (`The requested URL returned error: 403`).
4. The stream is not a valid tarball → `gzip` / `tar` error → installer reports download failure → **RUN fails** → entire image build fails.

**Root cause**

The **Cursor Agent CLI install path used in the image is not reliably fetchable in CI/unauthenticated contexts**: the resolved download URL returns **403 Forbidden**. That is an external availability/access policy issue for the artifact host (or the `/lab/` path), not a transient flake in our repo scripts alone.

**Implication for fix direction**

- Pin or replace how Cursor Agent is installed for release builds (e.g. a documented public artifact, vendored tarball, optional skip in CI, or an install method that does not depend on URLs that return 403 without credentials).
- Confirm with Cursor whether `downloads.cursor.com/.../lab/...` is intended to be publicly accessible for automated Docker builds.

