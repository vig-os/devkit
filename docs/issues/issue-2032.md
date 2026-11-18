---
type: issue
state: open
created: 2026-11-04T06:48:51Z
updated: 2026-11-04T06:48:51Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2032
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:28.172Z
---

# [Issue 2032]: [BASE_SHA audit follow-ups from #2031 (injected fold step, smoke-test dispatch, trunk rollback base, lag message)](https://github.com/vig-os/devkit/issues/2032)

Follow-ups from the review of #2031 (#2028). None blocked the merge.

1. **Two unpinned commit-action calls the static audit can't see:**
   - the fold step that `assets/init-workspace.sh` (~2441) injects, which is still on v0.3.2;
   - `assets/smoke-test/.github/workflows/repository-dispatch.yml` (~362).
   Neither writes content computed from an earlier checkout of its target. Pin them, or document why not, bump the injected one to v0.3.3, and extend the test to scan the injected and smoke-test sources.
2. **Trunk rollback base.** Under trunk, the rollback commit uses the main checkout SHA as base but targets the release branch. It's reachable only if deleting the branch failed, and then it fails closed. Pin it to the release-branch head, or drop the path.
3. **Lag message.** When freeze_wait times out because of ref lag, rollback says dev "advanced". Use wording that also covers the lag case, and add tests for lag that later clears and for the timeout message.
4. **Test parity.** Give the root rollback replay the same 4 cases as the consumer.

Refs: #2028
