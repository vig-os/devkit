---
type: issue
state: open
created: 2026-06-08T13:42:30Z
updated: 2026-06-08T14:25:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/559
comments: 0
labels: feature, priority:medium, area:image, area:workflow, effort:medium, semver:minor
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-09T06:16:00.007Z
---

# [Issue 559]: [[FEATURE] Single source of truth for container tool versions](https://github.com/vig-os/devcontainer/issues/559)

## Description

Introduce a single declarative file (e.g. `versions.json` or a `[tools]` table) as the source of truth for tool versions installed in the devcontainer image. Today, the `Containerfile` installs many tools from `releases/latest` while `tests/test_image.py` maintains separate `EXPECTED_VERSIONS` pins as a deliberate version-approval gate. When upstream releases drift, CI breaks and a human must manually bump the test pin and CHANGELOG — as seen in [#557](https://github.com/vig-os/devcontainer/issues/557).

A centralized versions file would let the Containerfile, tests, and documentation all read from one place, and Renovate could manage bumps as reviewable PRs (the real human-approval moment) instead of post-hoc breakage.

## Problem Statement

- Tool versions are duplicated across `Containerfile` (install logic), `tests/test_image.py` (`EXPECTED_VERSIONS`), and `README.md` / `docs/templates/README.md.j2` (documentation).
- The `Containerfile` installs bare-`releases/latest` for `gh`, `just`, `taplo`, `cargo-binstall`, `typstyle`, etc., so builds are not reproducible and version drift is discovered only after CI fails.
- README already embeds stale versions (e.g. "Python 3.12" while the image ships 3.14.5).

## Proposed Solution

1. Add a declarative versions file (e.g. `versions.json`) listing each tool, its pinned version, and install source.
2. Update the `Containerfile` to install pinned versions from that file instead of `releases/latest`.
3. Generate or read `EXPECTED_VERSIONS` in `tests/test_image.py` from the same file.
4. Render tool versions in `README.md` / `docs/templates/README.md.j2` from the same file (via `generate-docs` or template substitution).
5. Configure Renovate (custom manager or github-releases datasource) to bump versions in the file, producing reviewable PRs that update install, tests, and docs together.

## Acceptance Criteria

- [ ] One versions file is the single source of truth for tool versions
- [ ] `Containerfile` installs pinned versions from the file (reproducible builds)
- [ ] Image tests read expected versions from the same file
- [ ] README / generated docs reflect versions from the same file
- [ ] Renovate proposes version bumps as PRs that update all consumers atomically
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

## Related Issues

- [#557](https://github.com/vig-os/devcontainer/issues/557) — stale `cargo-binstall` pin exposed the duplication problem

**Changelog Category**: Changed
