---
type: issue
state: open
created: 2026-11-03T09:57:30Z
updated: 2026-11-03T09:57:30Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2001
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:58.867Z
---

# [Issue 2001]: [promote-release: follow-ups from the #1992 review (retry on PR lookup, fork PR filter, test gap, docs wording)](https://github.com/vig-os/devkit/issues/2001)

Follow-ups from the review of #1992 (#1990). None of them blocked promoting 1.18.1.

1. **Retry dropped from the release-PR lookup.** #1992 removed the `retry` wrapper around `gh pr list` in both the validate and merge jobs. In merge this happens AFTER publish: a transient API error fails the merge job and cleanup is skipped. Restore `retry`.
2. **Fork PRs can block a version.** `gh pr list --head release/X.Y.Z` also matches PRs from forks, and the repo is public. Anyone could open and close a fork PR from `release/X.Y.Z` into main, and the recovery path would then refuse that version ("found 2"). It fails safe, but filter on `isCrossRepository == false`.
3. **Untested branch.** Deleting the validate `if [ "$PR_STATE" = MERGED ]; then exit 0; fi` still passes every test, because the fake `gh pr view` always answers MERGEABLE/CLEAN. Live merged PRs answer UNKNOWN/UNKNOWN. Make the fake answer UNKNOWN for merged PRs.
4. **Docs wording.** RELEASE_CYCLE and the CHANGELOG say to dispatch "from main or dev". Until the fix reaches main, only a branch containing it works. Say "a branch containing the fix".

Refs: #1990
