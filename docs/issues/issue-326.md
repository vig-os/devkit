---
type: issue
state: closed
created: 2026-03-16T10:37:13Z
updated: 2026-03-16T16:56:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/326
comments: 0
labels: feature, priority:medium, area:ci, area:workflow, effort:medium, semver:minor
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:05.543Z
---

# [Issue 326]: [[FEATURE] Reusable release cycle workflows for downstream projects with safe customization](https://github.com/vig-os/devcontainer/issues/326)

## Description

Implement a reusable release cycle for downstream repositories, mirroring this project's release flow while allowing project-specific customization without workflow drift.

## Problem Statement

Downstream projects need a consistent release process, but they also need custom steps (for example: GHCR publishing, special packaging, or extra artifact publishing). Copying full workflows across repos causes drift and weakens upgradeability.

## Design Evaluation

### Option A (recommended): Core reusable workflows + downstream extension workflow contract

- This project ships and maintains reusable `prepare-release` and `release` workflows.
- Downstream repos call these workflows pinned to a tag/ref.
- Downstream repos own a local extension workflow (project-specific, not managed by this project), similar ownership model to `assets/workspace/justfile.project`: tracked locally and preserved by default.
- Core `release` workflow calls that extension workflow at a defined hook point and enforces a clear interface/contract.

**Pros**
- Centralized updates to shared release logic.
- Clear customization boundary.
- Lowest drift for common release behavior.

**Cons**
- Contract versioning/migrations must be managed.
- Requires robust docs and validation for extension hook usage.

### Option B: Fully downstream-owned workflow (no extension hook, no central updates)

- Each downstream project owns and maintains its own full release workflow.

**Pros**
- Maximum flexibility.

**Cons**
- Highest drift and maintenance burden.
- Repeated bugfixes and inconsistent release safety.

### Option C: Centrally shipped workflow file copied into downstream and merged manually

- This project periodically updates a downstream-tracked workflow file; users resolve updates with git merges.

**Pros**
- Familiar git-based update model.

**Cons**
- Still prone to divergence.
- Merge overhead increases over time.
- Ambiguous ownership of local edits vs upstream updates.

## Recommendation

Adopt **Option A**.

1. Keep shared release correctness in centrally maintained reusable workflows.
2. Keep project-specific behavior in a downstream-owned extension workflow.
3. Version the extension contract and document upgrade paths.

## Proposed Solution

Implement two reusable workflows in this project:

1. **`prepare-release`** reusable workflow
   - Performs common preparation steps.
   - Produces standardized outputs consumed by `release`.

2. **`release`** reusable workflow
   - Performs common validate/finalize/build/test orchestration.
   - Calls a downstream extension workflow (if configured) for project-specific steps.
   - Publishes the GitHub Release in exactly one canonical step owned by core workflow logic.

### Release Publication Rule (single-step requirement)

- The **actual GitHub Release creation/publish must occur once in core `release` workflow**, not inside extensions.
- Extension workflow is for custom project actions (e.g. GHCR/package/signing/artifact preparation), but must not create the GitHub Release object.
- Core workflow should fail clearly if extension fails.

This preserves one authoritative publish step while still enabling customization.

## Acceptance Criteria

- [ ] `prepare-release` and `release` are available as reusable workflows for downstream repos.
- [ ] `release` supports calling a downstream extension workflow through a documented contract.
- [ ] Contract versioning strategy is defined (for example: `contract_version`) and validated.
- [ ] Missing/invalid extension configuration fails with actionable error messages.
- [ ] GitHub Release publication occurs exactly once in a canonical core step.
- [ ] Documentation explains downstream integration, pinning strategy, and upgrade process.
- [ ] At least one downstream example demonstrates custom steps (for example: GHCR publishing).
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Implementation Notes

- Treat reusable workflows as the productized release engine.
- Treat extension workflow as downstream-owned customization layer.
- Downstream should pin reusable workflow refs to released tags for predictable behavior.
- Document how downstream projects adopt new workflow versions and contract changes.

## Related Issues

- Related to #310

## Changelog Category

Added


