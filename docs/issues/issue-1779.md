---
type: issue
state: open
created: 2026-09-29T15:45:19Z
updated: 2026-09-29T15:53:55Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1779
comments: 1
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1772
children: none
synced: 2026-09-30T08:17:39.467Z
---

# [Issue 1779]: [[FEATURE] PyPI publish lane: Trusted Publishing + PEP 740 attestations in publish-release.yml](https://github.com/vig-os/devkit/issues/1779)

### Description

Implementation of the PyPI channel for the publish-lane spike #1769 (review on #1772). This is the `pypi` job in the managed `publish-release.yml`, covering pure-Python and PyO3/maturin repos.

### Problem Statement

Python repos, including Rust+Python ones such as tessera, have no PyPI lane. Every adopter would hand-write Trusted Publishing, attestations and version mapping.

### Proposed Solution

- **Managed:** the `pypi` job composite, which uses `pypa/gh-action-pypi-publish` with PEP 740 attestations (**not** `uv publish`, which produces no attestations) and a skip-if-exists precheck.
- **Byte identity:** it publishes the same wheels and sdist that were uploaded to the draft Release in the assets window (download from the Release, do not rebuild), so attestations stay continuous.
- **Seeded:** a `just dist-pypi` recipe (`uv build`, or a `PyO3/maturin-action` matrix for native/abi3 wheels) and a `pyproject.toml` hint for a dynamic version backend (`hatch-vcs`, `setuptools-scm` or `uv-dynamic-versioning`) with a PEP 639 licence expression.
- **Release candidates:** published to production PyPI as PEP 440 prereleases (`1.2.3rc1`); not TestPyPI.
- **Docs:** a one-time pending-publisher registration against `publish-release.yml` and the `pypi` environment.

### Alternatives Considered

`uv publish --trusted-publishing` (no attestations); TestPyPI for release candidates (pruned, not a staging channel); cibuildwheel for PyO3 (maturin-action is the canonical tool).

### Additional Context

Pitfalls: a deleted PyPI filename can never be reused; the mapper from the skeleton issue must reject formats PEP 440 can't express.

### Impact

Python repos get PyPI publishing by declaring `DEVKIT_PUBLISH=pypi`, plus a one-time registration.

### Changelog Category

Added

Refs: #1769, #1772

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:53 PM_

**Revised after the ADR review on PR #1785** (`docs/rfcs/ADR-publish-lanes.md`):
- **The bytes come from the new asset builder, #1786.** It runs `just dist-pypi`, uploads to the draft and attests. This job downloads those exact wheels and sdist from the published Release and does not rebuild. Now blocked by #1786.
- **v1 is finals only.** The shared `resolve` job refuses prereleases. Publishing release candidates to PyPI as prereleases (`1.2.3rc1`) moves to #1787.
- Register the trusted publisher against `publish-release.yml` + environment **`publish-pypi`** (not `pypi`).

