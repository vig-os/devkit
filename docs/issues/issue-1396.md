---
type: issue
state: open
created: 2026-08-08T19:56:03Z
updated: 2026-08-08T19:56:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1396
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-09T03:48:34.574Z
---

# [Issue 1396]: [[BUG] smoke-test failure-notify job cannot mint its upstream App token (404)](https://github.com/vig-os/devkit/issues/1396)

Split from #1391 (its only unresolved part). The listener's `Notify upstream on smoke-test dispatch failure` job fails at **Generate release app token for upstream issue creation**:

```
RequestError [HttpError]: Not Found
```

Observed on every listener failure in the 1.7.0 train (runs 31207370105, 31217441944, 31275371280), so no upstream failure issue is ever filed in devkit. Likely the `create-github-app-token` mint requests `owner: vig-os`/`repositories: devkit` with an App that is not installed on devkit, or the wrong client-id secret is wired for the cross-repo case. Asset: `assets/smoke-test/.github/workflows/repository-dispatch.yml` (notify job).

Refs: #1391
