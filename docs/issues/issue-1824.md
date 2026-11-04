---
type: issue
state: open
created: 2026-10-05T18:35:52Z
updated: 2026-10-05T18:35:52Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1824
comments: 0
labels: feature, priority:medium, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:51:01.284Z
---

# [Issue 1824]: [install.sh --mode direnv/bare still requires a container runtime](https://github.com/vig-os/devkit/issues/1824)

## Problem
`install.sh --mode direnv` (and `--mode bare`) still requires podman or docker. The scaffold always runs `init-workspace.sh` inside the devcontainer image, even when the chosen mode produces no container files at all.

## Impact
A bare Nix host without a container runtime cannot adopt the delivery mode designed for it. It works today only on hosts that happen to have podman installed. Without a runtime, the installer prints container-runtime install instructions, which is the wrong remedy for a direnv adopter.

## Repro
On a host with `nix` and `direnv` but no podman/docker:
```bash
curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash -s -- --mode direnv --workflow trunk .
```

## Proposed
- When the mode is `direnv` or `bare` and `nix` is on PATH, run the scaffold from the flake instead of the image, e.g. a `nix run github:vig-os/devkit/<version>#init-workspace -- …` app.
- Otherwise, document in README "Requirements" that every mode, direnv included, needs a container runtime for installation.

