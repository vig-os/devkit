---
type: issue
state: closed
created: 2026-10-11T14:02:38Z
updated: 2026-10-12T11:24:08Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1861
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:42.969Z
---

# [Issue 1861]: [direnv mode still needs Docker: ci.yml's Scaffold Drift job re-scaffolds inside ghcr.io/vig-os/devcontainer via docker](https://github.com/vig-os/devkit/issues/1861)

## What happened
gerchowl/claude-config (devkit 1.18.0, `DEVKIT_MODE=direnv`) moved CI onto a self-hosted NixOS runner (`DEVKIT_CI_RUNNER`). Lint and Tests run fine through the Nix dev shell, but `Scaffold Drift` fails on every PR (run gerchowl/claude-config 38142791858):

```
Authenticating to ghcr.io as 'gerchowl'
…/_temp/….sh: line 8: docker: command not found
##[error]Process completed with exit code 127.
```

The job runs `docker login ghcr.io`, `docker pull $IMAGE` (`drift-image` = `ghcr.io/vig-os/devcontainer:1.18.0`) and `docker run --rm …` to re-scaffold, then diffs. So a direnv-mode consumer still depends on a container runtime on its CI runner.

## Expected (owner requirement)
A repo must be able to use devkit **strictly direnv-only**: no Docker or Podman anywhere in its CI or local workflow when `DEVKIT_MODE=direnv`. The drift check (and any other job) should run the pinned scaffold through Nix in that mode, e.g. `nix run github:vig-os/devkit/${VERSION}#install -- --version ${VERSION} --force --skip-preflight .` in a scratch copy, then diff, the same command consumers use to upgrade.

## Workaround in use
The consumer's Linux self-hosted runners get podman with docker compatibility (fleet-side). It's acceptable there, but not a substitute for a Docker-free direnv mode, and darwin runners have no container runtime.

Related: #1860 (self-hosted runners: resolve-toolchain's sparse checkout leaves the shared workspace unmaterialized), #1173, #1796.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 12, 2026 at 11:24 AM_

Fixed in #1870 (merged into dev): in direnv mode, Scaffold Drift re-scaffolds by running the pinned version's init-workspace.sh from its flake source in a scratch clone under RUNNER_TEMP. No container is involved, and container modes are unchanged. The remaining Docker dependency in direnv mode (install.sh and devkit-upgrade.yml) is tracked in #1871.

