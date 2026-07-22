---
type: issue
state: open
created: 2026-07-21T18:16:49Z
updated: 2026-07-21T18:16:49Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1248
comments: 0
labels: bug, priority:blocking, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:36.771Z
---

# [Issue 1248]: [install.sh --docker ownership repair breaks scaffold under rootless-podman docker shim](https://github.com/vig-os/devkit/issues/1248)

## Description

The #1235 ownership repair keys on the runtime CLI *name* (`RUNTIME = "docker"`), not the actual engine. On a host where `docker` is the rootless-podman compat shim (e.g. NixOS `virtualisation.podman.dockerCompat`), `install.sh --docker`:

1. scaffolds via container-root, whose output rootless podman already maps to the invoking user (correct, no repair needed), then
2. runs the repair `chown -R $(id -u):$(id -g)` **inside** the rootless container — where the host UID maps to an unmapped subuid on the host.

Result: the whole tree flips from correctly-owned to subuid-owned (`stat` shows `UNKNOWN UNKNOWN`), the host-side git phase fails (`fatal: not a git repository`), and the user needs `sudo chown` to recover. A regression of the #1235 fix: the same invocation with the 1.4.0 installer produces a correctly-owned, git-initialized tree.

## Reproduction (1.4.1-rc1 validation, 2026-07-21)

Host: NixOS-style, rootless podman 5.8.2, `docker` = podman shim.

```
$ ./install.sh --version 1.4.1-rc1 --skip-pull --docker --mode direnv ... <dir>   # rc1 installer
  -> owner UNKNOWN UNKNOWN, git phase failed
$ bash install-1.4.0.sh --version 1.4.0 --skip-pull --docker ... <dir>            # 1.4.0 installer, same host
  -> owner carlosvigo, git repo initialized
```

Mechanism proof — in-container chown maps to a subuid under either CLI:

```
$ docker run --rm -v "$t:/w" <image> bash -c 'touch /w/f; chown 1000:100 /w/f'
$ stat -c '%u %U' $t/f
100999 UNKNOWN
```

## Expected Behavior

The repair must run only when the scaffold output actually needs it. Condition on the **observed state**, not the CLI name: after the scaffold container exits, check whether the tree is owned by the invoking user; only if not, run the chown repair. This fixes real docker (root-owned output) and is a no-op under any rootless-podman flavor, shim or not.

## Impact

Release-blocking for 1.4.1: shipping it breaks `--docker` installs on rootless-podman shim hosts that work on 1.4.0 (the vigo-nixos deploy targets are exactly such hosts).

