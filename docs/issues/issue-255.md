---
type: issue
state: open
created: 2026-03-11T07:37:14Z
updated: 2026-06-23T06:56:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/255
comments: 1
labels: docs, effort:small, area:docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:55.419Z
---

# [Issue 255]: [[DOCS] Document Nix flake as alternative dev environment setup](https://github.com/vig-os/devcontainer/issues/255)

### Description

The project provides a `flake.nix` with a dev shell containing all required dependencies, plus a `.envrc` for direnv integration, but neither `CONTRIBUTE.md` nor `README.md` mention Nix as a setup option.

Update the Requirements/Setup section in `docs/templates/CONTRIBUTE.md.j2` to document:
- Nix flake as an alternative to manual package installation
- The experimental features that must be enabled (`nix-command`, `flakes`) — either via `~/.config/nix/nix.conf` or the `--extra-experimental-features` flag
- Optional direnv integration via the existing `.envrc`

### Documentation Type

Update existing documentation

### Target Files

- `docs/templates/CONTRIBUTE.md.j2` (source template)

### Acceptance Criteria

- [ ] Template adds a "Nix (alternative)" section alongside the existing Ubuntu/macOS install instructions
- [ ] Documents how to enable `nix-command` and `flakes` experimental features
- [ ] Documents `nix develop` usage and optional direnv setup
- [ ] Generated `CONTRIBUTE.md` regenerated with `just docs`

### Changelog Category

Changed

### Additional Context

The `flake.nix` and `.envrc` were added without corresponding documentation. Users encountering Nix for the first time hit `error: experimental Nix feature 'nix-command' is disabled` with no guidance.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Superseded by #633 (part of #625), which switches `.envrc` to nix-direnv and documents the clone → `direnv allow` flow + the Cachix substituter in `docs/templates/CONTRIBUTE.md.j2`, plus enabling the `nix-command`/`flakes` experimental features. Will close when #633 lands.

