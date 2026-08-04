---
type: issue
state: closed
created: 2026-08-04T07:43:44Z
updated: 2026-08-04T10:03:17Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1336
comments: 1
labels: bug, priority:medium, area:ci, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:54.182Z
---

# [Issue 1336]: [fix(workspace): trunk-model consumers keep baseBranchPatterns [dev] — Renovate inert](https://github.com/vig-os/devkit/issues/1336)

### Description

The shipped Renovate preset (`assets/workspace/.github/renovate-default.json`) hardcodes `baseBranchPatterns: ["dev"]`. The scaffold's trunk transform (`render_workflow_model()` in `assets/init-workspace.sh`) retargets `dev` → `main` only inside the workflow `.yml` files (anchored seds over `$wf/*.yml`); it does not touch `renovate-default.json`, and `scripts/transforms.py` has no baseBranch handling. A `DEVKIT_WORKFLOW=trunk` consumer therefore keeps `["dev"]` while having no `dev` branch.

Renovate restricted to a base-branch pattern that matches no existing branch has nothing to operate on — so Renovate is **effectively inert** on trunk consumers: no updates at all, including for the consumer-owned extension seams and any repo-authored files.

**Verified live** (2026-08-04): `exo-pet/vault` and `vig-os/org-config` both carry `"baseBranchPatterns": ["dev"]` in their scaffolded preset, yet their only long-lived branch is `main`.

### Expected Behavior

Trunk-model consumers get a preset with `baseBranchPatterns: ["main"]` so Renovate operates on their default branch.

### Proposed Fix

Render `baseBranchPatterns` per workflow model at scaffold/upgrade time: extend `render_workflow_model()` (or add a transform) to rewrite `["dev"]` → `["main"]` in `renovate-default.json` under `DEVKIT_WORKFLOW=trunk`, mirroring the existing dev→main retarget for workflows. Cover with a workflow-model test.

### Additional Context

Found during the #1332 sanity check (see that issue's plan); scoped out of PR #1335 for minimal diff. Known affected consumers today: `exo-pet/vault`, `vig-os/org-config`, and `exo-pet/exo-fleet` (all trunk). After the fix ships, their next `devkit-upgrade` corrects the preset automatically (it is a managed file).

---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 10:02 AM_

Fixed on dev via PR #1339 (merge 1ca3a505): trunk render retargets the renovate preset baseBranchPatterns to main. Ships with 1.6.0.

