---
type: issue
state: open
created: 2026-10-13T03:34:54Z
updated: 2026-10-13T03:34:54Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1880
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:38.630Z
---

# [Issue 1880]: [CI extension label checks: add labeled/unlabeled triggers and read-only caller permissions](https://github.com/vig-os/devkit/issues/1880)

Consumer: gerchowl/cue#63, PR gerchowl/cue#91, devkit 1.18.0.

The managed `.github/workflows/ci.yml` pull_request trigger has no `labeled`/`unlabeled` event types. A consumer-owned CI extension that checks the `no-changelog` label cannot refresh its warning immediately when that label changes. Please add `labeled`/`unlabeled` trigger types (with suitable concurrency behavior; related #1698 concerns the separate release-neutral guard).

There is also a permission prerequisite for runtime label lookup on a re-run. The managed `extension` calling job explicitly grants only:

```yaml
permissions:
  contents: read
  packages: read
```

A consumer cannot grant `issues: read` or `pull-requests: read` in `ci-extension.yml`: reusable workflows cannot elevate their caller's token permissions. `GET /repos/{owner}/{repo}/issues/{issue_number}/labels` requires one of those read permissions on this private repository. Please provide an upgrade-safe caller permission grant for this read-only use case, alongside the trigger change.

Expected behavior: the consumer extension can fetch current labels with the job's GITHUB_TOKEN, and label edits trigger a fresh check without modifying devkit-managed files. API failures remain hard errors; there is no fallback to stale event labels or a separate credential.

Sources:
- https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#supported-keywords-for-jobs-that-call-a-reusable-workflow
- https://docs.github.com/en/rest/issues/labels#list-labels-for-an-issue

Searched existing issues for labeled/unlabeled CI triggers and extension permissions; #1698 is about a different workflow and #1761 is about extension aggregation.

