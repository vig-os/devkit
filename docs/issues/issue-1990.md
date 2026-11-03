---
type: issue
state: open
created: 2026-11-03T09:07:53Z
updated: 2026-11-03T09:07:53Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1990
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T09:20:21.885Z
---

# [Issue 1990]: [promote-release: recover when the release PR was merged by hand before promote](https://github.com/vig-os/devkit/issues/1990)

promote-release.yml requires an OPEN release PR from `release/X.Y.Z` to main. Both the validate gate and the merge job run `gh pr list --head release/X.Y.Z --base main`, which lists open PRs only.

If someone approves and then merges the release PR by hand before promote runs, GitHub deletes the release branch. The workflow then can't be dispatched from `release/X.Y.Z` ("No ref found"), and from any other ref the PR lookup finds 0 PRs. Promote can no longer complete:
- `:latest` is never moved;
- the draft GitHub Release is never published;
- RC cleanup never runs.
There is no documented recovery.

Seen with 1.18.1: release PR #1969 was approved and merged by hand at 2026-11-03T09:06Z. Tag 1.18.1 exists, and devkit-smoke-test has published its final 1.18.1 release, but the devkit release is still a draft.

Acceptance:
- When no open PR exists, promote accepts a MERGED PR from `release/X.Y.Z` into main, but only if all of these hold:
  - it had an approving review (reviewDecision APPROVED, or an APPROVED review on its final head);
  - its merge commit is on main;
  - tag X.Y.Z is an ancestor of main.
  Every other existing validate check stays as it is: images, cosign, draft release, :latest never moving backwards, downstream final release.
- The merge job skips the merge when the PR is already merged, and still succeeds, so cleanup runs.
- The workflow can be dispatched from main or dev when the release branch is gone.
- Tests cover open, merged-approved and merged-unapproved (refused) PRs, closed-unmerged PRs (refused), and no PR at all (refused).
- RELEASE_CYCLE.md documents the recovery and says not to merge the release PR by hand.

Refs: #1969
