---
type: issue
state: open
created: 2026-04-02T13:29:30Z
updated: 2026-04-02T13:36:51Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/479
comments: 0
labels: bug, area:workflow, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-03T04:35:48.179Z
---

# [Issue 479]: [[BUG] publish-candidate recipe sends unknown "create-release" input to upstream release.yml](https://github.com/vig-os/devcontainer/issues/479)

### Description

The `publish-candidate` recipe in `justfile.gh` passes `-f "create-release=..."` to `release.yml`, but the upstream workflow does not declare a `create-release` input. GitHub rejects the dispatch with HTTP 422.

Introduced in commit `ad09ebd` ([Refs: #463](https://github.com/vig-os/devcontainer/issues/463)), which added `create-release` to the downstream `assets/workspace/.github/workflows/release.yml` and updated **both** `justfile.gh` files, but did not add the corresponding input to the upstream `.github/workflows/release.yml`.

### Steps to Reproduce

1. `just publish-candidate 0.3.2`

### Expected Behavior

Workflow dispatch succeeds and triggers the release candidate pipeline.

### Actual Behavior

```
could not create workflow dispatch event: HTTP 422: Unexpected inputs provided: ["create-release"]
```

### Environment

- **OS**: Ubuntu (Linux 6.17)
- **gh CLI**: latest
- **Branch**: `release/0.3.2`

### Additional Context

Audit of all release recipes against their workflows:
- `prepare-release` → `prepare-release.yml`: OK
- `finalize-release` → `release.yml`: OK
- `promote-release` → `promote-release.yml`: OK
- **`publish-candidate` → `release.yml`: sends `create-release` which the upstream workflow does not accept**

The downstream template (`assets/workspace/.devcontainer/justfile.gh`) has the same recipe, but its `release.yml` declares `create-release`, so it is not affected.

### Possible Solution

Either:
a) Remove the `create-release` parameter and `-f` flag from the upstream `justfile.gh` `publish-candidate` recipe (if the upstream workflow doesn't need it), or
b) Add the `create-release` input to `.github/workflows/release.yml` to match the downstream template.

### Changelog Category

Fixed

### TDD

- [ ] TDD compliance (see .cursor/rules/tdd.mdc)
