# Running Tests

This directory contains the image and integration test suites for the
devcontainer, plus the lightweight "shape" tests that need no container.

## Overview

The container-backed tests support running from two environments:

1. **Host machine** — direct podman access with bind mounts
2. **Inside a devcontainer** — Docker-out-of-Docker (DooD) via the podman socket

When running from inside a devcontainer, the test infrastructure automatically:

- Detects the container environment
- Uses `podman` with named volumes for workspace initialization
- Translates container paths to host paths using `HOST_WORKSPACE_PATH`

## Image under test

Integration and image tests run against a single image, selected by the
`TEST_CONTAINER_TAG` environment variable (default `dev`, the tag `just build`
loads the freshly-built Nix image under). The `just test`/`just test-integration`
recipes set it for you.

This matters for the `devcontainer up` tests: the scaffolded
`docker-compose.yml` pins the runtime image as
`ghcr.io/vig-os/devcontainer:${DEVCONTAINER_VERSION:-latest}`, and
`initialize.sh` writes the scaffolded `.vig-os` version (a *published* release)
into `.devcontainer/.env`. To keep the suite validating the image under test
rather than a stale published image, the `devcontainer_up` fixture exports
`DEVCONTAINER_VERSION=TEST_CONTAINER_TAG`.
Compose resolves shell environment variables ahead of `.env`, so the
freshly-built tag wins; `devcontainer exec` calls inherit the same environment.
To point the suite at a different build, set `TEST_CONTAINER_TAG` to that tag
(the image must already be loaded into podman). Refs #701.

## Prerequisites

### From host

```bash
# Install dependencies
uv sync

# Ensure the devcontainer image is built (loads the :dev tag into podman)
just build
```

### From inside a devcontainer

Basic tests need no special configuration. For **devcontainer CLI tests**
(which start nested devcontainers), the `HOST_WORKSPACE_PATH` environment
variable is required so container paths can be translated for the host's
podman daemon.

**For THIS devcontainer** (developing the devcontainer itself), it is
**automatically set** via `remoteEnv` in `.devcontainer/devcontainer.json`:

```json
"remoteEnv": {
    "HOST_WORKSPACE_PATH": "${localWorkspaceFolder}"
}
```

**For other devcontainers**, set it manually:

```bash
export HOST_WORKSPACE_PATH=/path/on/host/to/workspace
```

Without `HOST_WORKSPACE_PATH`, devcontainer CLI tests are skipped.

## Test execution

```bash
# All suites (container tests + shape tests + bats + renovate validation)
just test

# Individual suites
just test-image             # tests/test_image.py (builds the dev image if needed)
just test-integration       # tests/test_integration.py (ditto)
just test-utils             # tests/test_utils.py (no container needed)
just test-install           # tests/test_install_script.py
just test-vig-utils         # packages/vig-utils/tests
just test-bats              # tests/bats/

# Specific files or tests (uv directly)
uv run pytest tests/test_image.py
uv run pytest tests/test_integration.py::TestDevContainerStructure
```

See `TESTING.md` at the repo root for the overall testing strategy, and
`tests/CLEANUP.md` for lingering-container cleanup
(`just clean-test-containers`).

## Test infrastructure

### Named volumes for Docker-out-of-Docker

When running from inside a devcontainer, workspace initialization uses
**named volumes** instead of bind mounts (the host's podman cannot see
container-local paths):

```bash
# What the fixtures do, in podman terms:
podman volume create test-workspace-XXXX
podman run -it --rm \
  -v test-workspace-XXXX:/workspace \
  ghcr.io/vig-os/devcontainer:dev \
  /root/assets/init-workspace.sh
# ...then copy the volume contents out to inspect results.
```

### Container detection

The fixtures detect a container environment via `IN_CONTAINER=true`,
`/.dockerenv` / `/run/.containerenv`, or `/proc/1/cgroup` contents.

### Path translation

With `HOST_WORKSPACE_PATH` set, `get_host_path()` translates container paths
to host paths for devcontainer CLI `--workspace-folder` arguments and volume
mounts in `docker-compose.project.yaml`.

## Troubleshooting

### "no such file or directory" volume-mount errors

You are running inside a container and a test tried to bind-mount a
container-local path. Basic tests handle this automatically (named volumes);
devcontainer CLI tests need `HOST_WORKSPACE_PATH`.

### Named volumes persist

Test volumes are cleaned up automatically. To remove leftovers manually:

```bash
podman volume ls -q | grep test-workspace | xargs -r podman volume rm
```
