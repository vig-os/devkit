---
type: issue
state: open
created: 2026-10-08T09:35:06Z
updated: 2026-11-03T09:56:39Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1851
comments: 1
labels: bug, area:workflow, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:24:03.464Z
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
---

# [Comment #1]() by [gerchowl]()

_Posted on November 3, 2026 at 09:28 AM_

Hit by a second consumer too (gitflow, private, Free org, 1.18.0). It also matters that **a consumer can't carry a local fix**: patching `promote-release.yml` fails the scaffold-drift gate (verified: it is the only drift). The choices are to stay blocked, or to set `DEVKIT_DRIFT_CHECK=false` and lose drift protection for every other managed file.

The patch there is tested against the live 403 (`gh: Upgrade to GitHub Pro ... (HTTP 403)` -> fallback taken). It applies to both copies of the gate (validate and merge):

```bash
if RULES_JSON=$(retry --retries 3 --backoff 5 --max-backoff 30 -- gh api \
  "repos/${GITHUB_REPOSITORY}/rules/branches/main" 2>"$RUNNER_TEMP/rules.err"); then
  REQUIRED_APPROVALS=$(echo "$RULES_JSON" | jq '[.[] | select(.type == "pull_request") | .parameters.required_approving_review_count // 0] | max // 0')
elif grep -q 'HTTP 403' "$RUNNER_TEMP/rules.err"; then
  REQUIRED_APPROVALS=1   # or 0 as proposed above; make it a knob?
else
  cat "$RUNNER_TEMP/rules.err" >&2; exit 1
fi
```

0 (the issue's proposal) vs 1: on a Free-plan repo with several members, the release PR is the only gate that devkit itself can enforce. Defaulting the fallback to 1 approval gives those repos a real review step, and a solo consumer could set it to 0. Note that `retry` spends its attempts on a 403 that won't change, so short-circuiting on 403 would save about 15 s per job.


