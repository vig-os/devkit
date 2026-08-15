---
type: issue
state: open
created: 2026-08-14T17:08:40Z
updated: 2026-08-14T17:08:41Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1522
comments: 0
labels: feature, area:workflow, effort:small
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-08-15T02:57:58.785Z
---

# [Issue 1522]: [[FEATURE] release.yml validate: count only the latest check run per name in the CI-green gate](https://github.com/vig-os/devkit/issues/1522)

Follow-up to #1516. `release.yml` validate counts **every** FAILURE/ERROR entry in the release PR head SHA's `statusCheckRollup`. When a superseded workflow run leaves stale FAILURE check runs attached to the same SHA (e.g. after a close/reopen re-run — reruns replay frozen event payloads and can be unfixable by construction), the gate refuses a branch that `gh pr checks` (latest-per-name dedup) correctly reports green. During the 1.10.0 train this forced deleting the superseded run to proceed.

Change: group the rollup by check name and evaluate only the most recent run of each, matching `gh pr checks` semantics. Same for the consumer `release-core.yml` if it shares the logic.

Refs: #1516
