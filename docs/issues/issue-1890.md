---
type: issue
state: open
created: 2026-10-14T20:04:33Z
updated: 2026-10-14T20:04:33Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1890
comments: 0
labels: docs
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:44.508Z
---

# [Issue 1890]: [docs: present direnv mode as container-free in the README, solo guide and installer](https://github.com/vig-os/devkit/issues/1890)

## What happened

A solo consumer (devkit 1.18.0, `--mode direnv --workflow trunk`, CI on self-hosted k3s ARC pods) adopted devkit
from the README and `docs/SOLO_ADOPTION.md` and ended up depending on podman and the devkit image, although
direnv mode needs neither:

- **README "Requirements"** lists VS Code, the Dev Containers extension and Podman/Docker, and says "That's it!".
  The fact that direnv runs without Docker/Podman (nix, jq, rsync) only appears as a comment inside a later
  code block.
- **The one-line install defaults to `both`**, so a Nix user who doesn't pass `--mode` gets `.devcontainer/` and a
  container-runtime preflight.
- **`docs/SOLO_ADOPTION.md`** recommends `--mode devcontainer` and mentions `direnv` only as an aside.
- **1.18.0's installer** refuses to run without podman/docker even for `--mode direnv` (fixed on dev by #1873,
  unreleased). Its drift job needs docker (#1861 / #1870, unreleased). So today the only container-free route is
  running `assets/init-workspace.sh` from the flake source by hand, with `TEMPLATE_DIR`, `VERSION_FILE` and
  `WORKSPACE_DIR` set, and that route isn't documented.

- **rsync is a host prerequisite**, although `init-workspace.sh` needs it and the point of direnv mode is a
  Nix-provided toolchain. Neither the devkit toolchain (`mkProjectShell`) nor devkit's own dev shell (which #1873
  runs the renderer in) includes it, so a container-free render works on a dev machine with `/usr/bin/rsync` and
  then fails on a Nix-only CI pod (`rsync: command not found`). We now ship `pkgs.rsync` in our `extraPackages`.

The behaviour fixes are on dev, except rsync, which belongs in the devkit dev shell and the toolchain. What's left is the docs: setup and discovery should make the split clear before
the user picks a mode.

## Expected

1. README "Requirements" split by delivery mode:
   - devcontainer / both: VS Code + Dev Containers + podman/docker;
   - direnv: nix (+ direnv), jq, rsync, and no container runtime.
2. The install docs say plainly which modes need a container runtime, in CI as well as locally (Scaffold Drift,
   devkit-upgrade.yml), and from which release on direnv is fully container-free.
3. `SOLO_ADOPTION.md` presents `direnv` as an equal choice (Nix hosts, self-hosted/k8s runners where the pod
   already is the container), not an aside.
4. Optional: in the release notes for the first release that ships #1870 and #1873, a short note for 1.18.0 direnv
   consumers that they can drop `DEVKIT_DRIFT_CHECK=false` and any podman-based workarounds.

Related: #1861, #1865, #1870, #1871, #1873.

