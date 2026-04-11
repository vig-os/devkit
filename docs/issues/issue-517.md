---
type: issue
state: closed
created: 2026-04-10T15:28:41Z
updated: 2026-04-10T16:13:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/517
comments: 0
labels: bug, priority:blocking, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-11T04:27:28.097Z
---

# [Issue 517]: [[BUG] Promote Release workflow fails — GITHUB_TOKEN cannot see draft releases](https://github.com/vig-os/devcontainer/issues/517)

### Description

The "Promote Release" workflow (`promote-release.yml`) always fails at the "Verify draft GitHub Release exists" step (step 9 in the `validate` job). The `GITHUB_TOKEN` used has only `contents: read` permission, which is insufficient to list draft releases via the GitHub API.

From the [GitHub API docs](https://docs.github.com/en/rest/releases/releases#list-releases): *"Only users with push access will receive listings for draft releases."* A token with `contents: read` does not have push access.

### Steps to Reproduce

1. Trigger the "Promote Release" workflow for any version (e.g., `0.3.3`)
2. Observe step 9 ("Verify draft GitHub Release exists") in the `validate` job
3. The step retries 5 times but never finds the draft release

### Expected Behavior

The `validate` job finds the existing draft GitHub Release and proceeds to the downstream verification gate.

### Actual Behavior

The step fails with: `ERROR: No GitHub Release for tag 0.3.3`

This has affected **every** promote run (0.3.2 run [#24131664402](https://github.com/vig-os/devcontainer/actions/runs/24131664402), 0.3.3 run [#24248688161](https://github.com/vig-os/devcontainer/actions/runs/24248688161)).

### Environment

- **CI:** GitHub Actions (`ubuntu-22.04`)
- **Workflow:** `.github/workflows/promote-release.yml`
- **Job:** `validate` (permissions: `contents: read, packages: read`)

### Possible Solution

Use a token with push-level access for the draft release check. Two options:

**Option A (simplest):** Change `contents: read` to `contents: write` in the `validate` job permissions.

**Option B (least privilege):** Generate the `RELEASE_APP` GitHub App token in the `validate` job and use it as `GH_TOKEN` for the "Verify draft GitHub Release exists" step.

### Changelog Category

Fixed

### Acceptance Criteria

- [ ] `promote-release.yml` `validate` job can see draft releases
- [ ] Promote Release workflow succeeds end-to-end for 0.3.3
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
