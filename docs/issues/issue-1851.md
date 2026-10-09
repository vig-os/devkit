---
type: issue
state: open
created: 2026-10-08T09:35:06Z
updated: 2026-10-08T09:35:06Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1851
comments: 0
labels: bug, area:workflow, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-09T08:49:27.826Z
---

# [Issue 1851]: [[BUG] promote-release validate fails on a private repo in a Free org: rules/branches/main answers 403](https://github.com/vig-os/devkit/issues/1851)

## What happens

The approval gate added in #1506 (`promote-release.yml`, **validate → Find and verify release PR**) runs

```
gh api "repos/${GITHUB_REPOSITORY}/rules/branches/main"
```

On a **private repo in an org on the GitHub Free plan**, this endpoint answers:

```
HTTP 403: Upgrade to GitHub Pro or make this repository public to enable this feature.
```

The call sits inside `retry` under `set -euo pipefail`, so validate fails and the release cannot be promoted. Approving the PR doesn't help, because the 403 comes before the approval check. Seen on devkit 1.18.0 in a trunk consumer. The release itself (prepare, final, draft and tag) completed fine.

## Expected

A 403 from the rules endpoint means rulesets aren't available on this plan, so there can be no ruleset-required approvals. Treat it like the classic-protection case: `REQUIRED_APPROVALS=0`, with a log line naming the plan limit, and leave any real protection to GitHub's own merge-time refusal. Re-check the same call in the **merge** job if it repeats the gate.

## Related

Same consumer and release: #1842 (changelog-freeze trailing newline), #1843 (sync-issues dispatched when disabled), #1850 (Release App needs checks:read / statuses:read).
