---
type: issue
state: open
created: 2026-07-14T16:51:08Z
updated: 2026-07-14T16:51:08Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1080
comments: 0
labels: refactor, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:20.234Z
---

# [Issue 1080]: [refactor(workspace): friendlier eval error for invalid node module version](https://github.com/vig-os/devkit/issues/1080)

Found during review of release PR #1068.

`nodeAttr = "nodejs_${toString version}"` — if `version` is mistakenly passed as a path or derivation, the eval error is Nix's generic "cannot coerce to string" rather than the module-scoped friendly throw used for other invalid inputs. Still fails at eval time; purely a diagnostics/ergonomics improvement.

**Suggested:** validate `version` is an int before interpolation and throw a module-scoped message.

**File:** `nix/modules/node.nix:32`

