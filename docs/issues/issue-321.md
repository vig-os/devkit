---
type: issue
state: closed
created: 2026-03-16T08:38:39Z
updated: 2026-03-16T09:06:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/321
comments: 0
labels: chore, priority:medium, area:ci, effort:small
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:05.895Z
---

# [Issue 321]: [[CHORE] Migrate GitHub Actions references off Node.js 20 runtime](https://github.com/vig-os/devcontainer/issues/321)

## Chore Type
CI / Build change

## Description
GitHub Actions warns that some pinned actions in this repository are still on Node.js 20 and will be forced to Node.js 24 by default starting June 2, 2026. We should proactively update pinned action SHAs/versions to Node.js 24-compatible releases to avoid breakage.

## Acceptance Criteria
- [ ] Identify workflows using action versions that currently run on Node.js 20
- [ ] Update pinned action SHAs/versions to releases that support Node.js 24
- [ ] Validate key workflows (`ci.yml`, `release.yml`, `security-scan.yml`) after updates
- [ ] Document any actions that cannot yet be upgraded and track follow-up work

## Implementation Notes
- Start with warnings observed in scheduled security scan runs (e.g., `actions/checkout`, `docker/build-push-action`, `docker/metadata-action`, `docker/setup-buildx-action`, `actions/download-artifact`).
- Keep SHA pinning policy intact while upgrading to Node.js 24-compatible versions.
- Reference upstream deprecation notice: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

## Related Issues
- Related to https://github.com/vig-os/sync-issues-action/issues/77

## Priority
Medium

## Changelog Category
No changelog needed

## Additional Context
- Warning observed in run: https://github.com/vig-os/devcontainer/actions/runs/23131883679
- This is intentionally separate from issue #320 (artifact handoff failure root cause)
