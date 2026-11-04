---
type: issue
state: open
created: 2026-11-03T09:28:10Z
updated: 2026-11-03T09:28:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1998
comments: 0
labels: bug, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:24:00.646Z
---

# [Issue 1998]: [Fresh direnv scaffold floats the vigos flake input, so the first shell entry warns about version skew](https://github.com/vig-os/devkit/issues/1998)

## Description

A fresh direnv scaffold pins `DEVKIT_VERSION` in `.vig-os` but **floats** the flake input `vigos.url = "github:vig-os/devkit"` (default branch). So the very first `direnv allow` warns about version skew.

## Problem Statement

Seen in `exoma-ch/ravmatic`, scaffolded on 2026-11-03 with the 1.18.0 image while devkit `main` was already at 1.18.1. The first shell entry printed:

```
WARNING: vigos: dev-shell toolchain is devkit 1.18.1, but .vig-os pins DEVKIT_VERSION=1.18.0.
         The scaffold and the vigos flake input deliver coupled halves of each release;
         run 'nix flake update vigos' (then reload the shell) to advance the toolchain.
```

The suggested fix (`nix flake update vigos`) moves the toolchain further from the scaffold, not back to it. The real fix is to pin `?ref=1.18.0`, plus `DEVKIT_FLAKE_PIN_ADVANCE=true` so upgrades move the pin. Every new consumer has to discover this by hand. The template comment ("FLOATS on the default branch so a fresh project works before its first pin") predates release pins plus `DEVKIT_FLAKE_PIN_ADVANCE` (#1752).

## Proposed Solution

On a fresh install, render `vigos.url = "github:vig-os/devkit?ref=<DEVKIT_VERSION>"` and set `DEVKIT_FLAKE_PIN_ADVANCE=true`. The scaffold and the toolchain then start coupled, and `devkit-upgrade` advances both. Keep the floating form only for `--version dev` / unreleased images.

## Related

#1263 (the skew warning), #1752 (pin advance), #1989.

