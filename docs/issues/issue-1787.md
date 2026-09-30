---
type: issue
state: open
created: 2026-09-29T15:53:04Z
updated: 2026-09-29T15:53:04Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1787
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1769
children: none
synced: 2026-09-30T08:17:35.142Z
---

# [Issue 1787]: [[FEATURE] Candidate publishing to registries (PyPI prerelease, npm next, OCI rc tags)](https://github.com/vig-os/devkit/issues/1787)

### Description

Deferred from `docs/rfcs/ADR-publish-lanes.md` §7 (spike #1769): a trigger that publishes **release candidates** to registries. The target policies are PyPI production prereleases (`1.2.3rc1`), npm `--tag next`, and OCI `X.Y.Z-rcN` images; crates.io stays off by default.

### Problem Statement

The managed `publish-release.yml` fires on `release: published`, and only `promote-release.yml` publishes a Release, which it does for finals only. Candidate draft pre-releases are **deleted** by promote's cleanup job, and tag-only candidates have no Release at all. So no candidate can ever reach a registry. v1's `resolve` job refuses prereleases on purpose.

### Proposed Solution

To be designed. The candidate direction:

- `release-core.yml`'s candidate path dispatches `publish-release.yml` (`workflow_dispatch`, with the App token so it triggers), passing the candidate tag.
- `resolve` gains a candidate mode that validates **against the tag**, not a Release: the tag exists, it matches the configured prerelease format, and it points at the finalize SHA.
- Channel jobs route prereleases through the version-spelling mapper (#1778): PEP 440 for PyPI, the `next` dist-tag for npm, `-rcN` tags for OCI.
- This must not reuse the finals path's irreversible assumptions. Candidate versions are still permanent on PyPI and npm.

### Alternatives Considered

- Stop deleting candidate pre-releases and publish them: changes the promote lifecycle and immutability semantics; evaluate.
- TestPyPI: rejected in the PyPI review (it is pruned and is not a staging channel).

### Additional Context

Blocked by #1778, which provides the managed file, the mapper and the resolve job.

### Impact

Downstream consumers can test release candidates from registries before a final release.

### Changelog Category

Added

Refs: #1769

