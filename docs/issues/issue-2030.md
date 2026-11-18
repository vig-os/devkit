---
type: issue
state: open
created: 2026-11-04T05:28:34Z
updated: 2026-11-04T05:28:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2030
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:28.515Z
---

# [Issue 2030]: [prepare-changelog unfreeze: follow-ups from the #2024 review](https://github.com/vig-os/devkit/issues/2030)

Follow-ups from the review of #2024 (#2003). None affects today's CHANGELOG.

- **(a)** A `## ` line inside a fenced code block in the TBD section ends the fold early. Make the scanner fence-aware. **(b)** The same applies to a column-0 `- ` line inside a fence.
- **(c)** `## [x](url) - TBD` and `## [x] - TBD (rc)` are refused as "released". Give an accurate message, or accept them.
- **(d)** If there are two TBD sections for the same version, only the first is folded. Fold all of them, or refuse.
- **(e)** Identical bullets inside Unreleased are silently merged. Keep them, or report the merge.
- **(f)** In the consumer copy, a comment sits above the wrong step.
- **(g)** When dev moved, the commit fails with GitHub's raw "not a fast forward". Add a hint to re-run the job.

Refs: #2003
