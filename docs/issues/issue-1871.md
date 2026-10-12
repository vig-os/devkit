---
type: issue
state: open
created: 2026-10-12T00:58:59Z
updated: 2026-10-12T00:58:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1871
comments: 0
labels: bug, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:43.411Z
---

# [Issue 1871]: [direnv mode: install.sh and devkit-upgrade.yml still require docker/podman to scaffold or upgrade](https://github.com/vig-os/devkit/issues/1871)

Found while fixing #1861 (PR #1870). The owner requires that a repo can use devkit **strictly direnv-only**: no Docker or Podman in CI or in the local workflow.

#1870 makes Scaffold Drift Docker-free in direnv mode by running `init-workspace.sh` from the pinned flake source. But:
- `install.sh` itself runs `docker` or `podman run` on the devcontainer image, so `nix run github:vig-os/devkit/<ver>#install` can't upgrade a direnv-only consumer without a container runtime.
- `devkit-upgrade.yml` runs `install.sh --docker`.

**Expected:** in direnv mode, scaffold and upgrade run `init-workspace.sh` from the pinned flake source on the host, the same way #1870's drift path does, with no container. Container modes keep the image path.
