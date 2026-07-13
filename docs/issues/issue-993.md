---
type: issue
state: closed
created: 2026-07-13T07:12:12Z
updated: 2026-07-13T07:33:50Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/993
comments: 1
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:54.021Z
---

# [Issue 993]: [Expose vig-utils console scripts host-side (dev-shell + pinned uv-tool path)](https://github.com/vig-os/devkit/issues/993)

### Description

`prepare-changelog` and `renovate-changelog-pr` (console scripts of
`packages/vig-utils`) are invoked bare by the scaffolded release workflows
(`release-core.yml`, `prepare-release.yml`, `renovate-changelog-build.yml`) but
are only available inside the devcontainer image — they are **not** in
`devTools` (`nix/devtools.nix`), so direnv-mode dev-shells lack them, and bare
mode has no install path at all. This blocks mode-aware release workflows
(#991) for the container-less modes.

### Acceptance Criteria

- [ ] `nix develop` (consumer `mkProjectShell` dev-shell and devkit's own shell)
      provides `prepare-changelog` and `renovate-changelog-pr` on PATH
- [ ] A documented, version-pinned host-native install path exists for bare
      mode (e.g. `uv tool install git+https://github.com/vig-os/devkit@<DEVKIT_VERSION>#subdirectory=packages/vig-utils`),
      consumable by the setup-devkit-toolchain composite
- [ ] Dev-shell/image parity covered by tests (flake checks / pytest)

### Implementation Notes

The image already bakes vig-utils via the flake's `vigUtils`
`buildPythonPackage` (flake.nix:516+). Adding it to `devTools` delivers it to
dev-shell + image + home module from one list — verify no PATH/priority
collisions with the image's Python env.

### Related Issues

Blocks #991 (host-mode release). Part of #988.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 07:33 AM_

Merged into the epic branch via #999. Dev-shell (devkit + consumer mkProjectShell) now exposes prepare-changelog / renovate-changelog-pr; bare-mode pinned uv-tool path documented in MIGRATION.md.

