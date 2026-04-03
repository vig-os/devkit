---
type: issue
state: open
created: 2026-04-02T16:34:44Z
updated: 2026-04-02T16:34:44Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/483
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-03T04:35:47.365Z
---

# [Issue 483]: [[BUG] prepare-release changelog commits silently skipped due to FILE_PATHS delimiter mismatch](https://github.com/vig-os/devcontainer/issues/483)

## Description

The `prepare-release.yml` workflow passes `FILE_PATHS` as space-separated values to `vig-os/commit-action@v0.2.0`, but the action splits on commas. The entire space-separated string is treated as a single non-existent path, silently skipped, and both commit steps succeed with "No files to commit" instead of creating the expected commits.

The prepare-release workflow is designed to:
1. Freeze the CHANGELOG on `dev` (Unreleased → `[X.Y.Z] - TBD` + fresh empty Unreleased), commit to `dev`
2. Create the release branch from `dev` (post-freeze)
3. Strip the empty Unreleased section from the release branch, commit to `release/X.Y.Z`

All commits use `commit-action` to bypass branch protection rulesets via GitHub App token.

Because both commit steps silently no-op, the release branch is created from the unfrozen `dev` SHA, and neither branch receives the expected changelog modifications.

## Steps to Reproduce

1. Trigger the "Prepare Release" workflow with version `0.3.2`
2. Both "Commit prepared CHANGELOG to dev via API" and "Commit stripped CHANGELOG to release branch via API" log "No files to commit"
3. Workflow reports success despite no commits being created

Evidence: [Run #23899040367, job Prepare Release Branch](https://github.com/vig-os/devcontainer/actions/runs/23899040367/job/69690773277)

## Expected Behavior

`commit-action` should commit both `CHANGELOG.md` and `assets/workspace/.devcontainer/CHANGELOG.md` to the target branches with the frozen/stripped content.

## Actual Behavior

`commit-action` receives `FILE_PATHS="CHANGELOG.md assets/workspace/.devcontainer/CHANGELOG.md"`, splits on `,`, gets a single path `"CHANGELOG.md assets/workspace/.devcontainer/CHANGELOG.md"` which doesn't exist, silently skips it, and returns "No files to commit" with exit code 0.

## Environment

- GitHub Actions, `ubuntu-22.04` runner
- `vig-os/commit-action@1bc004353d08d9332a0cb54920b148256220c8e0` (v0.2.0)
- Workflow: `.github/workflows/prepare-release.yml`

## Possible Solution

Change both `FILE_PATHS` values in `prepare-release.yml` from space-separated to comma-separated:

```yaml
# Before
FILE_PATHS: CHANGELOG.md assets/workspace/.devcontainer/CHANGELOG.md
# After
FILE_PATHS: CHANGELOG.md,assets/workspace/.devcontainer/CHANGELOG.md
```

## Changelog Category

Fixed

## Acceptance Criteria

- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
