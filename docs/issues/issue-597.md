---
type: issue
state: closed
created: 2026-06-18T12:14:54Z
updated: 2026-06-19T06:30:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/597
comments: 0
labels: bug, priority:high, area:ci, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-19T07:20:03.613Z
---

# [Issue 597]: [Smoke-test prepare-release fails on empty Unreleased; template validation diverged from root (#590)](https://github.com/vig-os/devcontainer/issues/597)

## Summary

The `0.3.6-rc1` candidate release succeeded, but the downstream **smoke-test failed** at its `prepare-release` step:

```
ERROR: CHANGELOG.md Unreleased section has no entries
```

The release artifact itself is fine (image built, published, deployed, CI/CodeQL green in the consumer). This is a release-orchestration / template gap, not a problem with the image.

Failed run: https://github.com/vig-os/devcontainer-smoke-test/actions/runs/27758285399

## Root cause

Two compounding issues:

**1. The smoke-test fixture has an empty `## Unreleased` section.**
The smoke-test repo is a synthetic fixture — nobody hand-authors changelog entries there — so its `## Unreleased` is always empty. The `prepare-release` validation requires Unreleased to have *entries*, so it can never pass on a no-op fixture deploy. Upstream `devcontainer` passed only because its Unreleased was populated (#576, #586–589, #590, #591, #583).

**2. The #590 fix did not fully propagate to the workspace template.**
`5d76b9e` / `bf51096` updated both the root workflow and the template, but left them divergent:

| File (main) | Strip step | Validation |
|---|---|---|
| `.github/workflows/prepare-release.yml` (root) | removed | new `uv run prepare-changelog validate` |
| `assets/workspace/.github/workflows/prepare-release.yml` (template) | removed | still old inline awk: *"Verify CHANGELOG has Unreleased section entries"* |

Adopters (smoke-test, part-registry) inherit the *no-strip* half of #590 but not the new validator — they still run the strict "must have entries" awk check.

## Proposed fix

- [ ] Bring the workspace template's CHANGELOG validation to parity with the root workflow (use `prepare-changelog validate`), so the two don't drift.
- [ ] Decide whether an **empty `## Unreleased`** should be tolerated for fixture / no-op releases, and make the smoke-test deploy seed a placeholder Unreleased entry if not (e.g. `- Smoke-test deploy of <version>`), so the smoke-test's `prepare-release` can always pass.

## Acceptance criteria

- Smoke-test `prepare-release` passes on a deploy that has no real changelog entries.
- Root and template `prepare-release` use the same CHANGELOG validation logic (SSoT).

Refs: #590

