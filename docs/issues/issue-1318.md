---
type: issue
state: open
created: 2026-07-30T21:58:17Z
updated: 2026-07-30T21:58:17Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1318
comments: 0
labels: docs, priority:medium, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-31T05:42:05.832Z
---

# [Issue 1318]: [docs(release): unfreeze runbook — a published downstream final is the train's point of no return (immutability tombstones)](https://github.com/vig-os/devkit/issues/1318)

Lesson from the 1.5.0 ghost (2026-07-30): org-enforced release immutability tombstones the tag name of any published-then-deleted release — devkit-smoke-test's 1.5.0 became permanently unusable, forcing the fully validated train to re-release as 1.5.1. Add to docs/RELEASE_CYCLE.md (restart/unfreeze guidance): finalize restarts are cheap only while every release object in the pipeline (devkit AND downstream smoke-test) is still a draft; once smoke publishes its final, the version is committed — restart means burning it. Also note drafts never tombstone (safe to delete freely). Refs: vig-os/devkit#1301, #1311.
