---
type: issue
state: closed
created: 2026-07-15T08:43:11Z
updated: 2026-07-15T14:37:13Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1106
comments: 1
labels: refactor, priority:medium, area:image, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 1103
children: none
synced: 2026-07-15T20:04:04.913Z
---

# [Issue 1106]: [Replace full podman runtime with DooD-only client (~254 MiB; sidecar model retired)](https://github.com/vig-os/devkit/issues/1106)

### Description

The image ships the **full `podman` local runtime** — `crun`, `criu`, `conmon`,
`netavark`, `passt`, `libkrun`/`libkrunfw`, `aardvark-dns`, `fuse-overlayfs`,
`runc`, plus `systemd`. Marginal cost (measured on `.#devkitImageEnv`):
**~254 MiB** across 62 paths.

The original justification — shipping heavy toolchains as **sidecars** (e.g.
geant4) via podman-in-podman — **has been retired**. Everything that remains is
**Docker-out-of-Docker (DooD)** against the *host* socket:

- the consumer scaffold itself:
  `assets/workspace/.devcontainer/scripts/initialize.sh:94-123` (runs
  host-side) discovers the host's rootless podman socket and mounts it as
  `/var/run/docker.sock`; `devcontainer.json` / `docker-compose.yml` set
  `DOCKER_HOST=unix:///var/run/docker.sock`;
- the `docker→podman` shim, `flake.nix:1043-1055`, honoring `DOCKER_HOST`;
- the test harness, `tests/README.md:10` — "DooD via podman socket → host's
  podman daemon";
- every `podman build/load/tag` in `justfile*` and CI
  (`.github/workflows/nix-image.yml`) runs **host-side**.

The full runtime is only needed to *run isolated containers inside the
container* (true DinD) — the retired sidecar use case. With DooD, `podman
build`/`run` forwards to the host socket; the container is a thin client.

### Proposed mechanism

Ship a **client-only podman**. Note: this pin has **no `podman-remote`
attribute**, and the wrapper's helper set is hardcoded
(`passthru.helpersBin` in `pkgs/by-name/po/podman/package.nix`: gvproxy,
aardvark-dns, netavark, passt, conmon, crun; `extraRuntimes` only *adds*).
Implementation options, to be settled in the PR:

1. `podman.override` replacing the helper inputs (crun/conmon/netavark/passt/
   aardvark-dns/gvproxy/fuse-overlayfs/runc) with an empty `symlinkJoin` or
   equivalent stubs, keeping the bare client binary + shell completions;
2. `overrideAttrs` on the wrapper to drop the helpers PATH suffix.

Keep the `docker→podman` shim as is (it execs the client, which honors
`DOCKER_HOST`).

Side effect: removes `criu` — **one of the four anchors** of the redundant
CPython 3.13 interpreter (see that sub-issue).

### Risk / contract

- Loses in-container **isolated** container execution (nested/local runtime).
  Per the epic's contract note this was never part of the image contract (the
  scaffold is DooD-wired out of the box) → **`semver:minor`**, with the epic as
  the declaration of record.
- **Check before landing**: audit `tests/`, `docs/CONTAINER_SECURITY.md`, and
  consumer scaffolds for anything invoking `podman run`/`build` *without* a
  host socket present.

### Verification

- `nix path-info -Sh .#devkitImageEnv` drops ~254 MiB; crun/criu/conmon/
  netavark/passt/libkrun*/aardvark-dns/fuse-overlayfs/runc/systemd gone.
- In the built image with the host socket mounted: `docker build` and
  `podman build` succeed against the host socket; the DooD test path passes.
- `podman --version` still works with no socket (client present, graceful
  error on daemonless operations).

### Notes

Part of the image-slimming epic. The overridden podman is not in
cache.nixos.org; first CI build pays, vig-os.cachix.org caches after.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:37 PM_

Implemented and merged to dev in #1122 (−67 MiB measured; estimate corrected on the epic — criu anchor removed as intended).

