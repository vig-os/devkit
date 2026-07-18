---
type: issue
state: open
created: 2026-07-17T20:27:07Z
updated: 2026-07-17T20:27:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1206
comments: 0
labels: chore, priority:high, area:ci, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:21.486Z
---

# [Issue 1206]: [workflow-model spike: prove trunk release cut-from-main + scaffold render](https://github.com/vig-os/devkit/issues/1206)

Part of #1205. **First step — de-risks the two riskiest assumptions before any production wiring.**

## Deliverables
1. **Trunk release topology proof.** On a throwaway repo, drive the rendered trunk `prepare-release` legs: freeze CHANGELOG on `main`, cut `release/X.Y.Z` from `main`'s post-freeze SHA (incl. the #617 wait-for-advance guard, now watching main), then the existing dev-free `release-core`/`promote-release` merge-back-to-`main` + tag. A local git simulation of these legs is acceptable for the spike (full live-CI is the later end-to-end verification). **Pass:** tag on main, PR merged to main, `## Unreleased` intact, no step touches `dev`.
2. **Scaffold render proof.** Prototype `render_workflow_model()` (anchored `dev→main` sed on `prepare-release.yml` + branch-filter files) + the `sync-main-to-dev.yml` copy-exclude, and show the rendered trunk workspace is actionlint-clean, has **zero residual `heads/dev`**, and doesn't break the `--force` preview mirror or the #991 bats invariants.
3. Red/green `tests/test_workflow_model.py` skeleton.

No production wiring in this issue — just the go/no-go proof + skeleton.

Refs: #1205
