---
type: issue
state: closed
created: 2026-07-30T21:58:17Z
updated: 2026-08-04T10:03:08Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1318
comments: 1
labels: docs, priority:medium, area:workflow, effort:small
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:58.166Z
---

# [Issue 1318]: [docs(release): unfreeze runbook — a published downstream final is the train's point of no return (immutability tombstones)](https://github.com/vig-os/devkit/issues/1318)

Lesson from the 1.5.0 ghost (2026-07-30): org-enforced release immutability tombstones the tag name of any published-then-deleted release — devkit-smoke-test's 1.5.0 became permanently unusable, forcing the fully validated train to re-release as 1.5.1. Add to docs/RELEASE_CYCLE.md (restart/unfreeze guidance): finalize restarts are cheap only while every release object in the pipeline (devkit AND downstream smoke-test) is still a draft; once smoke publishes its final, the version is committed — restart means burning it. Also note drafts never tombstone (safe to delete freely). Refs: vig-os/devkit#1301, #1311.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 06:08 AM_

Solved by PR #1320 (merged to dev 2026-07-30): RELEASE_CYCLE runbook now documents that a published downstream final is the train's point of no return — finalize restarts after that point tombstone the smoke tag via release immutability. Closing manually (dev-PR Closes doesn't auto-close).

