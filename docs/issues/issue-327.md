---
type: issue
state: closed
created: 2026-03-16T11:13:25Z
updated: 2026-03-16T13:11:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/327
comments: 0
labels: chore, priority:medium, area:ci, area:workspace, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:05.208Z
---

# [Issue 327]: [[CHORE] Consolidate workspace CI to ci workflow and remove obsolete setup-env action](https://github.com/vig-os/devcontainer/issues/327)

## Chore Type
CI / Build change

## Description
`assets/workspace/.github/workflows/ci.yml` is no longer necessary. Release `0.3.0` validated that these CI actions can run directly in a containerized workflow.

The workspace CI should be consolidated into `assets/workspace/.github/workflows/ci-container.yml`, and that workflow should be renamed to `ci` as the single CI entrypoint.  
`assets/workspace/.github/actions/setup-env/` appears obsolete after this consolidation and should be removed if no references remain.

## Acceptance Criteria
- [ ] `assets/workspace/.github/workflows/ci.yml` is removed
- [ ] `assets/workspace/.github/workflows/ci-container.yml` is renamed/replaced to be the canonical `ci` workflow
- [ ] All workspace CI jobs execute through the containerized CI workflow only
- [ ] `assets/workspace/.github/actions/setup-env/` is removed if unused
- [ ] No remaining references to removed workflow/action paths
- [ ] CI passes after workflow consolidation

## Implementation Notes
- Update workflow filenames and any references (`uses`, docs, scripts, release/process docs) to the new canonical CI workflow path.
- Verify whether `setup-env` has any remaining consumers before removal.
- Prefer minimal diff scoped to workspace CI templates.

## Related Issues
Related to #326

## Priority
Medium

## Changelog Category
Changed

## Additional Context
Release `0.3.0` demonstrated that CI can run directly in a container, making the separate legacy CI workflow and setup action unnecessary.
