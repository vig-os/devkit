---
type: issue
state: closed
created: 2026-10-12T00:58:59Z
updated: 2026-10-12T12:32:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1871
comments: 1
labels: bug, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:42.454Z
---

# [Issue 1871]: [direnv mode: install.sh and devkit-upgrade.yml still require docker/podman to scaffold or upgrade](https://github.com/vig-os/devkit/issues/1871)

Found while fixing #1861 (PR #1870). The owner requires that a repo can use devkit **strictly direnv-only**: no Docker or Podman in CI or in the local workflow.

#1870 makes Scaffold Drift Docker-free in direnv mode by running `init-workspace.sh` from the pinned flake source. But:
- `install.sh` itself runs `docker` or `podman run` on the devcontainer image, so `nix run github:vig-os/devkit/<ver>#install` can't upgrade a direnv-only consumer without a container runtime.
- `devkit-upgrade.yml` runs `install.sh --docker`.

**Expected:** in direnv mode, scaffold and upgrade run `init-workspace.sh` from the pinned flake source on the host, the same way #1870's drift path does, with no container. Container modes keep the image path.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 12, 2026 at 12:32 PM_

Fixed in #1873 (merged into dev). In direnv mode, install.sh scaffolds and upgrades on the host: it runs init-workspace.sh inside the pinned release's own dev shell under `env -i`, starting from the scratch dir. The version comes from the .vig-os pin, or resolves to the newest X.Y.Z tag on a fresh install. devkit-upgrade.yml drops `--docker` for direnv repos and passes the job token to nix. The smoke lane installs nix first. Container modes are unchanged. Consumers get a container-free upgrade only once their target release ships this install.sh.

