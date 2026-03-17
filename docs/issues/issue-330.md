---
type: issue
state: open
created: 2026-03-16T16:54:15Z
updated: 2026-03-16T16:54:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/330
comments: 0
labels: feature, priority:medium, area:ci, area:workflow, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:04.826Z
---

# [Issue 330]: [[FEATURE] Allow downstream release extension to pass assets and release notes to publish workflow](https://github.com/vig-os/devcontainer/issues/330)

## Description

Enable downstream `release-extension.yml` workflows to contribute release payload data (artifacts, checksum files, and optional release notes override) to the canonical publish step in `release-publish.yml`.

## Problem Statement

The current downstream release architecture correctly centralizes final GitHub Release creation in `release-publish.yml`, but extension jobs run in separate workflow-call context and cannot directly pass generated files or note content into publish.

As a result, downstream customization can build/sign assets, but cannot reliably:
- attach artifacts (e.g. binaries, `.sha256`) to the final GitHub Release
- override/augment release notes generated from `CHANGELOG.md`

## Proposed Solution

Introduce a new workflow contract version (e.g. `contract_version: "2"`) that allows controlled handoff from extension to publish while preserving a single canonical release creation step.

Suggested contract additions:
- Optional extension output/artifact channel for release assets (including checksum files)
- Optional release notes override input consumed by publish
- Backward-compatible fallback behavior:
  - if override/asset channel is absent, publish behaves exactly as today
  - release notes continue to default to `CHANGELOG.md`

## Acceptance Criteria

- [ ] Extension can provide one or more files for release attachment (including `.sha256`)
- [ ] Publish workflow uploads those files to the created GitHub Release
- [ ] Extension can optionally provide release notes override; publish uses it when present
- [ ] Default changelog-derived notes remain the fallback when override is absent
- [ ] Contract mismatch fails with actionable error
- [ ] Existing `contract_version: \"1\"` downstream setups remain supported or have a documented migration path
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Alternatives Considered

- Keep extension as gate-only and require post-release manual upload/edit:
  - Simpler contract but poor automation and higher release drift
- Let extension create the release object:
  - Rejected because it breaks the single canonical publish-step design

## Additional Context

Related to #326 (reusable downstream release workflows contract).
Builds on #310 behavior (final release notes publication).

Potential docs to update:
- `docs/DOWNSTREAM_RELEASE.md`
- `docs/RELEASE_CYCLE.md`

## Impact

This is a backward-compatible enhancement to downstream release customization boundaries:
- improves parity for projects that publish binaries/packages/checksums
- keeps one authoritative release creation step in core publish flow
- reduces manual release editing/upload work in downstream repos

## Changelog Category

Changed
