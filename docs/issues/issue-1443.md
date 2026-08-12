---
type: issue
state: closed
created: 2026-08-12T08:43:22Z
updated: 2026-08-12T09:32:09Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1443
comments: 1
labels: bug
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:41.231Z
---

# [Issue 1443]: [[BUG] Smoke deploy commit drops installer deletions — retired scaffold paths survive and fail the drift gate](https://github.com/vig-os/devkit/issues/1443)

## What happened

The 1.8.0-rc1 smoke-test dispatch failed at \`Wait for deploy PR merge\` (run 31578823294, upstream notification #1442): deploy PR devkit-smoke-test#356 could not auto-merge because its **Scaffold Drift** check failed.

## Root cause

devkit 1.8.0 retires \`.github/workflows/renovate-changelog-build.yml\` and \`renovate-changelog-commit.yml\` (#1423), listed in the retired-paths manifest (#1348). The installer correctly removed both from the runner's working tree — the deploy log shows the DELETIONS report:

```
The following 2 path(s) will be DELETED:
  ✗  .github/workflows/renovate-changelog-build.yml (retired scaffold path — #1348)
  ✗  .github/workflows/renovate-changelog-commit.yml (retired scaffold path — #1348)
```

But the deploy step publishes the tree via \`vig-os/commit-action\` (\`FILE_PATHS: .\`), which builds the commit **additively** from working-tree contents and cannot express file deletions. The two retired workflows silently survived on the deploy branch, and the drift gate (correctly) rejected the PR — its second live catch after #1344.

## Why only the smoke lane

The consumer adoption path is not affected: \`devkit-upgrade.yml\` publishes via the git tree API with explicit \`sha: null\` deletion entries. Only \`assets/smoke-test/.github/workflows/repository-dispatch.yml\` has the gap.

## Fix

Add a deletion-publishing step to the smoke dispatch template after the commit-action commit: compute \`git ls-files --deleted\` (in smoke mode the installer's \`rsync --delete\` + overlay makes the working tree exactly the fresh render, so this set is precisely what the new scaffold no longer ships) and publish a verified commit on the deploy branch using the same tree-API \`sha: null\` pattern \`devkit-upgrade.yml\` already uses.

The running listener executes from devkit-smoke-test's default branch, so the fixed template also needs a manual redeploy there before the next candidate dispatch.

Refs: #1442, #1423, #1348
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 09:32 AM_

Fixed by PR #1445, merged into release/1.8.0 @3b2aa344 (closing manually — Closes on a non-default-branch PR doesn't auto-close). The listener redeploy to devkit-smoke-test main landed via devkit-smoke-test#357. Live proof rides the 1.8.0-rc2 dispatch (run 31583273344), which must publish the two retired-workflow deletions to the deploy branch and pass the Scaffold Drift gate.

