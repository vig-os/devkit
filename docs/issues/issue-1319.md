---
type: issue
state: closed
created: 2026-07-30T21:58:19Z
updated: 2026-08-04T10:03:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1319
comments: 1
labels: feature, priority:low, area:workflow, effort:small
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:57.761Z
---

# [Issue 1319]: [feat(workflow): promote gate should detect the smoke-tag immutability tombstone and fail with the real cause](https://github.com/vig-os/devkit/issues/1319)

The cross-repo gate in promote-release.yml says 'wait for the smoke-test workflow to publish its final release, then retry' when no downstream release exists — but when the tag name is tombstoned (published release deleted under org-enforced immutability, see the 1.5.0 ghost), waiting is futile. The smoke publish attempt fails with GH013 'creations restricted'. Teach the gate (or the smoke release publish step) to recognize this state and fail with 'version burned — re-cut required' instead. Refs: vig-os/devkit#1301.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 06:08 AM_

Solved by PR #1321 (merged to dev 2026-07-30, stacked on #1320): the promote gate now detects the smoke-tag immutability tombstone (GH013) and fails with the real cause instead of an opaque error. Closing manually (dev-PR Closes doesn't auto-close).

