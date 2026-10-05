---
type: issue
state: open
created: 2026-09-29T15:45:15Z
updated: 2026-09-29T15:53:44Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1778
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1769
children: none
synced: 2026-09-30T08:17:39.973Z
---

# [Issue 1778]: [[FEATURE] Managed publish-release.yml + DEVKIT_PUBLISH declaration (registry publish lane foundation)](https://github.com/vig-os/devkit/issues/1778)

### Description

Implementation of `docs/rfcs/ADR-publish-lanes.md` §1, §2 and §6 (spike #1769). This covers the **managed top-level `publish-release.yml`**, the `DEVKIT_PUBLISH` declaration, the frozen environments, the version-spelling mapper, a freeze test, and the docs rewrite. Channel jobs (PyPI #1779, crates.io #1748, npm #1781) plug into it.

*Revised after the ADR review on PR #1785. The environment names and branch policy changed, v1 is finals only, the concurrency group was renamed, the overlap preflight moved earlier, and the freeze test and docs now have an owner here.*

### Problem Statement

Registry Trusted Publishing binds to the **top-level caller workflow filename**, optionally plus an environment name, and none of the registries accepts reusable workflows (reviews on #1771, #1772, #1773). The lane must therefore be one fixed-name file in each consumer repo, and its names are **forever contracts**. Today the only post-publish seam is the seeded, repo-owned `publish-release-extension.yml`, so fixes can never propagate.

### Proposed Solution

- **`assets/workspace/.github/workflows/publish-release.yml`** (managed):
  - **Triggers:** `release: published`, and `workflow_dispatch` with inputs `tag` and optional `channel`. Retries are dispatched from the default branch.
  - **`resolve` job:** checks that the Release is published and **refuses prereleases**; v1 is finals only (ADR §7, #1787).
  - **Channel jobs:** ids `pypi`, `crates`, `npm`, each gated on `DEVKIT_PUBLISH`, each body a devkit composite action. v1 ships the jobs as inert placeholders; the channel issues fill them.
  - **Concurrency:** group `registry-publish-<tag>`. **Not** `publish-release`, which promote and abandon already use.
- **Environments:** frozen names `publish-pypi`, `publish-crates` and `publish-npm`, distinct from the `pypi` / `crates-io` names the seeded extension's header suggests.
  - Create an environment **only if it is absent**, with no required reviewers and a deployment-branch policy that allows the release tags **and the default branch** (for retries).
  - **Never modify an existing environment.**
  - Probe the environments API first. If the scaffold can't create them, document them as a one-time manual step.
- **`.vig-os` `DEVKIT_PUBLISH`:** a declaration seeded from evidence, following the `DEVKIT_LANGUAGES` contract. Values: `pypi`, `crates`, `npm`, `oci`, `binaries`. Evidence rules are in ADR §2. Undeclared channels ship nothing (#1519).
- **Removing a channel** drops its job, but the file stays. The scaffold warns and links the registry's revoke UI.
- **Overlap preflight** (the extension file publishing the same channel): runs at scaffold/upgrade time **and** in promote's `validate` job, before the point of no return. It is a best-effort grep, so it warns rather than fails.
- **Version-spelling mapper** (vig-utils): the train version mapped to SemVer, PEP 440 and an npm dist-tag. It refuses `DEVKIT_PRERELEASE_FORMAT` values PEP 440 can't express when `pypi` is declared. In v1 it only validates, and it is used by #1787.
- **Freeze test:** pins the filename, job ids, environment names and concurrency group, so a rename fails CI.
- **Docs:**
  - Rewrite the "Publish Extension Hook" section of `docs/DOWNSTREAM_RELEASE.md` and the header comment of `publish-release-extension.yml` so it points at the managed lane.
  - Add the lane to `docs/RELEASE_CYCLE.md`.
  - Document that moving a channel from the extension file to the managed file needs a new registry registration.

### Alternatives Considered

See ADR §Alternatives: one file per channel, reusable workflows for registries, extending the seeded extension, reviewer-gated or reused environment names, a tag-only deployment rule.

### Additional Context

Frozen by the ADR: `publish-release.yml`, the job ids, the environment names. Never make a breaking change to them.

### Impact

This is the foundation for #1779, #1748, #1781 and #1787. Consumers that declare nothing get an inert file and nothing else.

### Changelog Category

Added

Refs: #1769

