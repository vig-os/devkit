---
type: issue
state: open
created: 2026-07-30T21:58:19Z
updated: 2026-07-30T21:58:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1319
comments: 0
labels: feature, priority:low, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-31T05:42:05.528Z
---

# [Issue 1319]: [feat(workflow): promote gate should detect the smoke-tag immutability tombstone and fail with the real cause](https://github.com/vig-os/devkit/issues/1319)

The cross-repo gate in promote-release.yml says 'wait for the smoke-test workflow to publish its final release, then retry' when no downstream release exists — but when the tag name is tombstoned (published release deleted under org-enforced immutability, see the 1.5.0 ghost), waiting is futile. The smoke publish attempt fails with GH013 'creations restricted'. Teach the gate (or the smoke release publish step) to recognize this state and fail with 'version burned — re-cut required' instead. Refs: vig-os/devkit#1301.
