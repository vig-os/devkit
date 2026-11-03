---
type: issue
state: open
created: 2026-11-02T04:45:41Z
updated: 2026-11-02T04:45:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1985
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-02T04:55:23.297Z
---

# [Issue 1985]: [abandon-release: also abandon the mirrored train in devkit-smoke-test](https://github.com/vig-os/devkit/issues/1985)

When a devkit release train is abandoned, `abandon-release.yml` cleans up devkit only. The mirrored `release/X.Y.Z` branch and its PR in the validation repo (`devkit-smoke-test`) stay behind.

The next train's smoke dispatch then fails in that repo's Prepare Release single-train guard: "Another release train is in flight: release/X.Y.Z".

Seen during 1.18.1-rc1:
- 1.19.0 had been abandoned in devkit.
- The smoke repo still had `release/1.19.0` and PR #448 open.
- The fix was to dispatch the smoke repo's Abandon Release for 1.19.0 by hand, then re-run the failed listener.

Acceptance:
- abandon in devkit also dispatches abandon in the validation repo, using the existing App and repository_dispatch, idempotently.
- Or, if that is out of scope, `docs/RELEASE_CYCLE.md` (Abandoning) lists the manual step.

Refs: #1969
