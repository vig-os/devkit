---
type: issue
state: open
created: 2026-10-07T16:05:44Z
updated: 2026-10-07T16:05:44Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1849
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-08T08:45:26.585Z
---

# [Issue 1849]: [promote-release leaves release/X.Y.Z behind; the next prepare-release then refuses as 'another train in flight'](https://github.com/vig-os/devkit/issues/1849)

## What happens

`promote-release.yml` merges the release PR into `main` and publishes the Release, but leaves `release/X.Y.Z` on the remote. The next `prepare-release.yml` then refuses:

```
ERROR: Another release train is in flight; a second train cannot be cut alongside it:
  release/0.1.0
Promote or abandon it first (just promote-release / just abandon-release), then retry
```

The 0.1.0 train **was** promoted: the release PR is merged and the GitHub Release is published. The only way forward is deleting the merged branch by hand, which the message doesn't suggest. (1.18.0; seen under trunk for 0.1.0 and again on the first gitflow train for 0.2.0.)

## Expected

One of:
- promote deletes `release/X.Y.Z` after merging (it is fully contained in `main`); or
- the in-flight check ignores a `release/*` branch that is an ancestor of `main` with a published Release for its tag, or at least names that case and the `git push origin --delete release/X.Y.Z` remedy.

