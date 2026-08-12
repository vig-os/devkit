---
type: issue
state: closed
created: 2026-08-12T12:02:46Z
updated: 2026-08-12T12:35:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1470
comments: 1
labels: refactor, priority:low, area:ci, effort:small, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:34.196Z
---

# [Issue 1470]: [[REFACTOR] remove the dead git_user_name/git_user_email plumbing from the scaffolded release workflows](https://github.com/vig-os/devkit/issues/1470)

### Description

#1462 (PR #1467) replaced the scaffolded orchestrator's rollback — previously a `git reset --hard $PRE_SHA` + force-push performed with a configured git identity — with the guarded Git Data API revert. That was the last consumer of the `git_user_name` / `git_user_email` values threaded through the scaffolded release workflows; the plumbing is now dead weight, deliberately left in place by #1467 to keep that PR's diff minimal.

### Scope

Remove the dead inputs and every site that declares or forwards them, consistently across the scaffolded workflow set (`assets/workspace/.github/workflows/`): the `release-core.yml` `workflow_call` input declarations and any use sites, the orchestrator `release.yml` caller that forwards them, and any other scaffolded workflow that still threads the pair. Map the actual set before cutting — #1467's review noted the removal ripples across three workflows.

### Compatibility consideration (why this is not a trivial deletion)

This is a `workflow_call` interface change on the consumer surface: a caller that passes an input the reusable workflow no longer defines fails validation. Orchestrator and core ship together via the scaffold and are updated together by devkit-upgrade, so skew is bounded — but the removal must land in caller and callee in the same release, and the changelog must flag it on the consumer surface (hence `semver:minor`).

### Tests

`tests/test_workflow_release_publish.py` currently asserts release-core still declares these inputs (retained by #1467's test rewrite). Flip those assertions first (TDD), then remove the plumbing.

Refs: #1462, #1467
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 12:35 PM_

Fixed by PR #1472, squash-merged into release/1.8.0 (release-branch merges don't auto-close). All dead git_user_name/git_user_email plumbing removed — four workflows in both devkit and scaffold copies (release.yml dispatch inputs + core forward, release-core.yml workflow_call declarations, prepare-release.yml inputs + extension forward, prepare-release-extension.yml seam declarations) plus the contract docs. Consumer-preserved extension copies verified zero-use; optional inputs with defaults keep stale copies valid against the upgraded caller. Pinned by absence assertions in test_workflow_release_publish.py / test_workflow_prepare_extension.py. Ships in 1.8.0.

