---
type: issue
state: open
created: 2026-03-20T17:07:36Z
updated: 2026-03-20T17:07:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/403
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:43.760Z
---

# [Issue 403]: [[BUG] Downstream smoke-test CHANGELOG diverges from workspace scaffold after release cycle](https://github.com/vig-os/devcontainer/issues/403)

### Description

The smoke-test dispatch workflow (`repository-dispatch.yml`) mismanages `CHANGELOG.md` in the downstream repo (`vig-os/devcontainer-smoke-test`). After a full release cycle, `main`'s `CHANGELOG.md` does not match the workspace scaffold shipped with the image (`assets/workspace/CHANGELOG.md`).

Two problems:

1. **Wrong source file**: The "Sync upstream CHANGELOG onto release branch" step downloads `vig-os/devcontainer/${TAG}/CHANGELOG.md` (the upstream *project* changelog with real version entries) instead of `assets/workspace/CHANGELOG.md` (the empty scaffold). This overwrites the release branch with content that has no relation to the downstream repo.

2. **No post-release reset**: After `prepare-release` and `release` workflows process their fake `## Unreleased` / `## [X.Y.Z] - TBD` lifecycle, nothing resets `CHANGELOG.md` on `main` back to the scaffold. The fake changelog entries accumulate on `main` across release cycles.

### Steps to Reproduce

1. Dispatch `smoke-test-trigger` with an RC tag (e.g., `0.3.1-rc9`)
2. Observe the deploy step creates a stub `CHANGELOG.md` with "Deploy devcontainer 0.3.1-rc9"
3. `prepare-release` freezes it to `## [0.3.1] - TBD`
4. The sync step overwrites with the upstream project's CHANGELOG (wrong file)
5. After the release PR merges, `main`'s `CHANGELOG.md` contains upstream version entries that don't belong in the downstream repo

### Expected Behavior

After the full release cycle completes, `CHANGELOG.md` on `main` in the downstream repo should be identical to the workspace scaffold (`assets/workspace/CHANGELOG.md`) -- just `## Unreleased` with empty category headers.

### Actual Behavior

`main`'s `CHANGELOG.md` contains either:
- The upstream project's full changelog (if the sync step succeeded), or
- Leftover fake entries from `prepare-release` (e.g., `## [0.3.1] - TBD` with "Deploy devcontainer 0.3.1-rc9")

Neither matches the scaffold. Current state of `main` in the downstream repo is an empty scaffold only because no release has fully completed yet.

### Environment

- **Template**: `assets/smoke-test/.github/workflows/repository-dispatch.yml` (lines 504-537)
- **Scaffold**: `assets/workspace/CHANGELOG.md`
- **Downstream repo**: `vig-os/devcontainer-smoke-test`

### Additional Context

The CHANGELOG sync step is also a source of merge conflicts between the release branch and `main`, contributing to #402. The `prepare-release` and `release-core` workflows require a valid `## [X.Y.Z] - TBD` entry to function, so the fake CHANGELOG cannot simply be replaced before those workflows run.

### Changelog Category

Fixed

- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
