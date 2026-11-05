---
type: issue
state: open
created: 2026-11-04T15:40:15Z
updated: 2026-11-04T15:40:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2048
comments: 0
labels: feature, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:45.189Z
---

# [Issue 2048]: [resolve-toolchain image probe needs a docker CLI on the runner; probe the registry without it](https://github.com/vig-os/devkit/issues/2048)

Found in review of #2046 (#2045).

The `resolve-toolchain` jobs run on `vars.CI_RUNNER_SMALL || vars.DEVKIT_CI_RESOLVE_RUNNER` directly, because they produce the gated output and so can't use it. In container-ish modes they run `docker login` and `docker manifest inspect`. No daemon is needed, but the docker **CLI** must exist.

On a self-hosted pool with no docker CLI, the probe fails with a misleading `::error::Failed to authenticate to ghcr.io`. That turns every container-mode run red, and the `DEVKIT_CI_CONTAINER_RUNNERS` gate cannot prevent it.

**Proposal:** probe the image through the OCI distribution API with `curl` (token exchange, then a `HEAD` request on the manifest), removing the docker CLI dependency. Or detect a missing CLI and report it accurately.

**Acceptance:** the resolver works on a runner with no docker CLI, or fails with an error that names the missing CLI.
