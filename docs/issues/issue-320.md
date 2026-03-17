---
type: issue
state: closed
created: 2026-03-16T08:29:03Z
updated: 2026-03-16T09:28:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/320
comments: 0
labels: chore, priority:high, area:ci, effort:small
assignees: c-vigo
milestone: 0.3.1
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:06.258Z
---

# [Issue 320]: [[CHORE] Fix scheduled security scan artifact handoff between jobs](https://github.com/vig-os/devcontainer/issues/320)

## Chore Type
CI / Build change

## Description
The `Scheduled Security Scan` workflow fails in the `Security Scan` job because it attempts to download `container-image-${version}-amd64`, but the `build-image` job in `security-scan.yml` does not upload that artifact.

## Acceptance Criteria
- [ ] `build-image` uploads `/tmp/image.tar` as `container-image-${{ steps.version.outputs.version }}-amd64`
- [ ] `security-scan` successfully downloads the uploaded artifact
- [ ] The scheduled workflow run completes without failing at `Download image artifact`
- [ ] Node 20 deprecation warnings are tracked separately (or addressed in this issue if you prefer)

## Implementation Notes
- Add an `actions/upload-artifact` step to `.github/workflows/security-scan.yml` after the image build step.
- Use the same artifact naming convention already used in `.github/workflows/ci.yml`.
- Keep retention/compression consistent with existing image-artifact usage.

## Related Issues
Related to CI reliability for scheduled security scans.

## Priority
High

## Changelog Category
No changelog needed

## Additional Context
Failing run: https://github.com/vig-os/devcontainer/actions/runs/23131883679
Error: `Unable to download artifact(s): Artifact not found for name: container-image-scheduled-2026-03-16-763be4a-amd64`
