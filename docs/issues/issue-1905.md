---
type: issue
state: open
created: 2026-10-20T17:07:34Z
updated: 2026-10-20T17:07:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1905
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-21T07:24:30.423Z
---

# [Issue 1905]: [release: ship #1870 (docker-free scaffold drift in direnv mode) for self-hosted runners without Docker](https://github.com/vig-os/devkit/issues/1905)

Consumers on self-hosted runners without a Docker daemon cannot run Scaffold Drift on devkit 1.18.0 (latest release, 2026-10-05): the job runs `docker pull` + `docker run` of `ghcr.io/vig-os/devcontainer:<ver>` and fails with `failed to connect to the docker API at unix:///var/run/docker.sock`.

Seen on the exo-pet ksb k3s ARC runners (pods have nix but no Docker, by design), e.g. exo-pet/data-analysis#14. #1870 (merged 2026-10-12) already runs drift through nix in direnv mode, but no release contains it yet.

Meanwhile the exo-pet consumers (exo-fleet, data-analysis, playground-carlos, vault, MPECT) set `DEVKIT_DRIFT_CHECK=false` with a reason comment, so the job reports skipped rather than passed. Restore it with the first upgrade past 1.18.0.

Related: #1897 (action-free CI spike, docker-free lanes), #1871 (install.sh/devkit-upgrade still need docker/podman in direnv mode).
