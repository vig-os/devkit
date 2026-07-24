---
type: issue
state: closed
created: 2026-07-20T16:51:33Z
updated: 2026-07-21T07:52:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1226
comments: 1
labels: chore, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:42.136Z
---

# [Issue 1226]: [Trunk render leaves prose dev mentions in scaffolded workflow comments/descriptions](https://github.com/vig-os/devkit/issues/1226)

Both live trunk switches (vig-os/org-config#64, exo-pet/exo-fleet#230) flagged the same cosmetic residue: `render_workflow_model()` deliberately retargets only functional literals, so a few prose mentions of `dev` survive in trunk-rendered files — `ci.yml` header ("Pull requests to dev, release/**, and main") and the origin/dev rationale comment (~L228), `codeql.yml` header, and the `sync-issues.yml` `target-branch` input description ("e.g., dev, release/x.y.z").

No functional impact (all functional values render to main), but every trunk consumer ships these slightly-lying comments. The #1206 spike already retargeted prepare-release's cosmetic step names, so extending the anchored render (or the doc comments themselves) to be model-neutral is consistent with precedent. Low priority.

Refs: #1205
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 07:52 AM_

Fixed by PR #1229, merged to dev (dev-targeted PRs don't auto-close). Trunk render now scrubs the four prose spots (ci.yml header + origin/dev rationale, codeql.yml header, sync-issues.yml target-branch description); gitflow render stays byte-identical. Review found one adjacent pre-existing gap, filed as #1233 (promote-release.yml sync-main-to-dev prose). Ships with 1.4.1.

