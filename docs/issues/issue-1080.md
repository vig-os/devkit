---
type: issue
state: closed
created: 2026-07-14T16:51:08Z
updated: 2026-07-14T21:02:13Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1080
comments: 1
labels: refactor, priority:low, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T04:57:32.092Z
---

# [Issue 1080]: [refactor(workspace): friendlier eval error for invalid node module version](https://github.com/vig-os/devkit/issues/1080)

Found during review of release PR #1068.

`nodeAttr = "nodejs_${toString version}"` — if `version` is mistakenly passed as a path or derivation, the eval error is Nix's generic "cannot coerce to string" rather than the module-scoped friendly throw used for other invalid inputs. Still fails at eval time; purely a diagnostics/ergonomics improvement.

**Suggested:** validate `version` is an int before interpolation and throw a module-scoped message.

**File:** `nix/modules/node.nix:32`

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:02 PM_

Shipped in [1.2.0](https://github.com/vig-os/devkit/releases/tag/1.2.0) via PR #1088.

