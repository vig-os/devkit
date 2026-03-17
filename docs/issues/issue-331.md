---
type: issue
state: open
created: 2026-03-16T17:05:56Z
updated: 2026-03-16T17:08:30Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/331
comments: 0
labels: feature
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-17T04:24:04.461Z
---

# [Issue 331]: [[FEATURE] Trigger downstream smoke-test release workflow from dispatch and gate upstream release on result](https://github.com/vig-os/devcontainer/issues/331)

## Description

When the upstream dispatch workflow is called, trigger the downstream smoke-test repository release workflow and enforce success as a required gate for upstream release completion.

## Problem Statement

The current release flow does not guarantee end-to-end validation of downstream release behavior before considering upstream release successful. This can allow upstream release jobs to pass while downstream integration/release logic fails.

## Proposed Solution

Extend the release workflow contract so that dispatch from upstream triggers the smoke-test downstream release workflow with version-aware behavior:

- For RC versions, downstream creates a pre-release
- For final versions, downstream creates a full release

Then make upstream release dependent on the downstream run outcome, failing upstream when downstream release fails.

## Alternatives Considered

- Keep downstream release as best-effort/non-blocking:
  - Simpler pipeline, but weak release confidence and can mask integration failures.
- Trigger downstream manually post-release:
  - Adds operational overhead and delays failure detection.

## Additional Context

Related to:
- #326 (reusable release workflows for downstream projects)
- #330 (downstream extension contract for publish data handoff)

Target repo for downstream validation: smoke-test repository.

## Impact

- Improves release safety by validating downstream release behavior during upstream release.
- Ensures RC and final release semantics are exercised consistently.
- Backward-compatible for consumers that do not enable downstream smoke-test integration (subject to contract defaults).

## Acceptance Criteria

- [ ] Upstream dispatch triggers downstream smoke-test release workflow automatically
- [ ] Version detection correctly maps RC versions to pre-release behavior downstream
- [ ] Version detection correctly maps final versions to full release behavior downstream
- [ ] Upstream release job requires downstream release workflow success before completing
- [ ] Failure in downstream release workflow causes upstream release workflow to fail with actionable logs
- [ ] Documentation updated for dispatch inputs, downstream contract, and gating semantics
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Changelog Category

Changed
