---
type: issue
state: closed
created: 2026-07-13T07:12:32Z
updated: 2026-07-13T08:04:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/994
comments: 1
labels: feature, area:ci, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:53.716Z
---

# [Issue 994]: [Shared setup-devkit-toolchain composite action (mode-aware step-level provisioning)](https://github.com/vig-os/devkit/issues/994)

### Description

New scaffolded composite action `.github/actions/setup-devkit-toolchain/action.yml`
— the single step-level toolchain preamble for every scaffolded workflow job.
Reads `DEVKIT_MODE` + `DEVKIT_VERSION` from `.vig-os` and branches:

- **container** → provisioning no-op: export `UV_PROJECT_ENVIRONMENT`,
  `PREK_HOME`, apply the `git safe.directory` fix, prek version-skew guard
  (all the container-only pieces currently inlined per job)
- **direnv** → `install-nix-action` + vig-os Cachix substituter +
  `nix develop --profile` on the repo's own flake, prepend dev-shell bins to
  `GITHUB_PATH` (the devkit's own `.github/actions/setup-env` pattern)
- **bare** → `astral-sh/setup-uv` + pinned `uv tool install` (rust-just, prek,
  vig-utils per #993), prepend to `GITHUB_PATH`

All host branches install the `retry` shim via `BASH_ENV` (from setup-env).
After the composite runs, plain `run: just sync` / `gh` / `prepare-changelog`
steps work identically in every mode — the choreography steps stay untouched.

### Acceptance Criteria

- [ ] Composite ships in `assets/workspace/.github/actions/` (all modes) and is
      exercised by per-mode bats render assertions
- [ ] Container branch reproduces today's in-container env exactly
- [ ] direnv/bare branches provide the full release tool set (just, uv, prek,
      retry, prepare-changelog, renovate-changelog-pr)
- [ ] Version-skew guards preserved per mode (#854)
- [ ] actionlint-clean (#995)

### Implementation Notes

Job-level `container:`/image selection stays OUTSIDE the composite — mechanism
decided by the #992 spike (Option A conditional container vs Option B
host-always for the release set).

### Related Issues

Depends on #992, #993. Consumed by #991. Part of #988.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 08:04 AM_

Merged into the epic branch via #1002. Both composites ship in every mode; review finding (silent host-mode fallback on corrupt DEVKIT_MODE) fixed with a closed validation case. Verified locally in the dev-shell: 150/150 bats green, full hook suite green.

