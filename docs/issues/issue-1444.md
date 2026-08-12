---
type: issue
state: closed
created: 2026-08-12T08:45:13Z
updated: 2026-08-12T09:32:12Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1444
comments: 1
labels: bug
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:40.876Z
---

# [Issue 1444]: [[BUG] Smoke dispatch template still generates dotted deploy branch names — reverts smoke#354 at every deploy](https://github.com/vig-os/devkit/issues/1444)

## What happens

\`assets/smoke-test/.github/workflows/repository-dispatch.yml\` still computes \`BRANCH_NAME="chore/deploy-${TAG}"\` (dotted, e.g. \`chore/deploy-1.8.0-rc1\`). The live listener on devkit-smoke-test \`main\` was hand-fixed to the dot-free form \`chore/deploy-${TAG//./-}\` (devkit-smoke-test#354) as a 1.8.0 train prerequisite, because the new scaffolded CI branch-name gate (#1432) allows chore branches only as \`^chore/[a-z0-9]+(-[a-z0-9]+)*$\` — dots are rejected.

But the fix never made it back into the template SSoT. Every smoke deploy overlays the template listener into the repo tree, so the 1.8.0 deploy PR reverts smoke#354; after this release merges to smoke \`main\`, the **next** train's deploy branch is dotted again and the deploy PR fails the branch-name gate — a guaranteed future train blocker.

## Fix

Port smoke#354 into the template: map dots to dashes in the deploy branch name (and carry its explanatory comment), so the SSoT and the live listener agree.

Found while diagnosing #1443 on the 1.8.0-rc1 dispatch failure.

Refs: #1432, #1443
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 09:32 AM_

Fixed by PR #1446, merged into release/1.8.0 @b60b306a (closing manually — Closes on a non-default-branch PR doesn't auto-close). The template SSoT now generates dot-free deploy branch names, matching the hand-fixed live listener (devkit-smoke-test#354); the 1.8.0-rc2 deploy will overlay the template without reverting the fix.

