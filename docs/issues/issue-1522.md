---
type: issue
state: closed
created: 2026-08-14T17:08:40Z
updated: 2026-08-17T10:57:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1522
comments: 1
labels: feature, area:workflow, effort:small
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:16.482Z
---

# [Issue 1522]: [[FEATURE] release.yml validate: count only the latest check run per name in the CI-green gate](https://github.com/vig-os/devkit/issues/1522)

Follow-up to #1516. `release.yml` validate counts **every** FAILURE/ERROR entry in the release PR head SHA's `statusCheckRollup`. When a superseded workflow run leaves stale FAILURE check runs attached to the same SHA (e.g. after a close/reopen re-run — reruns replay frozen event payloads and can be unfixable by construction), the gate refuses a branch that `gh pr checks` (latest-per-name dedup) correctly reports green. During the 1.10.0 train this forced deleting the superseded run to proceed.

Change: group the rollup by check name and evaluate only the most recent run of each, matching `gh pr checks` semantics. Same for the consumer `release-core.yml` if it shares the logic.

Refs: #1516
---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 10:57 AM_

Fixed in #1537 (merged to dev): the CI-green gate now dedups statusCheckRollup into a latest-per-name set (recency key startedAt — completedAt is null mid-run and would rank a live re-run oldest) and derives all three counts from it, matching gh pr checks semantics. Applied to all six gate sites: release.yml validate, both promote-release.yml gates (devkit + scaffold), and the consumer release-core.yml. Executable fixture tests cover the #1516 scenario per site. Follow-up candidates noted in the PR: StatusContext entries still always count pending (pre-existing, now pinned), and gh_issues.py _dedupe_status_checks still keys on completedAt.

