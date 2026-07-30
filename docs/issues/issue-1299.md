---
type: issue
state: open
created: 2026-07-30T09:02:32Z
updated: 2026-07-30T09:02:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1299
comments: 0
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T11:51:50.243Z
---

# [Issue 1299]: [ci: runner-image podman 5.8.4 + stale system crun breaks every podman run in image testinfra](https://github.com/vig-os/devkit/issues/1299)

## Symptom

Nix Image (discovery) run [30528291013](https://github.com/vig-os/devkit/actions/runs/30528291013) (dev @4772c62f, merge of #1298) failed on the **amd64** leg: all 116 portable testinfra tests errored at container start with

```
Error: OCI runtime error: crun: unknown version specified
```

The arm64 leg passed. The same commit's content is workflow-template-only — the image is unaffected.

## Root cause

The failure is a GitHub runner-image regression, not devkit code:

- Last green dev run ([30516144283](https://github.com/vig-os/devkit/actions/runs/30516144283), 05:15Z): runner image `ubuntu-24.04 20260720.247.2`, preinstalled `podman 4.9.3`.
- Failing run (08:50Z): runner image `ubuntu-24.04 20260726.254.1`, preinstalled `podman 5.8.4`.

podman ≥ 5 writes OCI runtime-spec v1.2.x `config.json`, which crun < 1.14.3 rejects with exactly this error (containers/podman#27272). The updated runner image bumped podman but the system crun stayed at Ubuntu 24.04's stale apt version, so every `podman run` dies at container start. Rollout is per-runner: PR CI of #1298 (~08:00Z) still drew an old runner and passed, so red is probabilistic until the fleet converges — then deterministic.

`setup-env` keeps podman on the host path by design (#632: rootless setuid newuidmap integration), so CI inherits whatever pairing the runner image ships.

## Fix

Pair the host podman with the flake's pinned crun instead of the runner's: the dev-shell closure already carries the crun that nixpkgs pairs with podman 5.8.x (crun 1.27.1, spec-v1.2-capable, backward-compatible with podman 4.x configs). In `setup-env`'s "Install podman" step, resolve `-crun-` from the dev-profile closure and write a rootless `containers.conf` drop-in (`~/.config/containers/containers.conf.d/`) pointing the `crun` runtime at that store path. The podman↔crun pairing is then pinned by `flake.lock`, immune to runner-image drift.

Blocks the 1.5.0 release train (release.yml runs the same test-image action).
