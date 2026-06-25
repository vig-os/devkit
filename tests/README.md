# Running Tests

This directory contains integration tests for the devcontainer setup.

## Overview

The tests support running from two environments:

1. **Host machine** - Direct podman access with bind mounts
2. **Inside devcontainer** - Docker-out-of-Docker (DooD) via podman socket

When running from inside a devcontainer, the test infrastructure automatically:
- Detects the container environment
- Uses `podman` with named volumes for workspace initialization
- Uses the shared workspace directory for temp files (accessible to both host and container)
- Translates container paths to host paths using `HOST_WORKSPACE_PATH`
- Handles all path translation transparently

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
rather than a stale published image, the `devcontainer_up` and
`devcontainer_with_sidecar` fixtures export `DEVCONTAINER_VERSION=TEST_CONTAINER_TAG`.
Compose resolves shell environment variables ahead of `.env`, so the
freshly-built tag wins; `devcontainer exec` calls inherit the same environment.
To point the suite at a different build, set `TEST_CONTAINER_TAG` to that tag
(the image must already be loaded into podman). Refs #701.

## Prerequisites

### From Host

```bash
# Install dependencies
uv sync --group test

# Ensure the devcontainer image is built
make build
```

### From Inside Devcontainer

When running tests from inside a devcontainer, **no special configuration is needed**. The test infrastructure will:

- Automatically detect it's running in a container
- Use `podman` with named volumes (avoiding host path issues)
- Handle the `init-workspace` test correctly

For **devcontainer CLI tests** (which start nested devcontainers), the `HOST_WORKSPACE_PATH` environment variable is required.

**For THIS devcontainer** (developing the devcontainer itself), this is **automatically set** via `remoteEnv` in `.devcontainer/devcontainer.json`:

```json
"remoteEnv": {
    "HOST_WORKSPACE_PATH": "${localWorkspaceFolder}"
}
```

VS Code expands `${localWorkspaceFolder}` to the host path automatically.

**For other devcontainers**, if you want to run these tests, you'll need to manually set:

```bash
export HOST_WORKSPACE_PATH=/path/on/host/to/workspace
```

Without `HOST_WORKSPACE_PATH`, devcontainer CLI tests will be skipped (but compose-based tests will still run).

## Test Execution

### Run all tests

```bash
# From host or container - works from both!
make test

# Or explicitly with uv
uv run pytest tests/
```

**Note**: When running from within the devcontainer, `HOST_WORKSPACE_PATH` is automatically set via `remoteEnv` in `devcontainer.json`, enabling full test functionality.

### Run specific test categories

```bash
# Integration tests only
make test-integration

# Image tests only
make test-image

# Registry tests only
make test-registry
```

### Run specific test files

```bash
uv run pytest tests/test_image.py       # ✓ Works from anywhere
uv run pytest tests/test_integration.py # ✓ Works from anywhere
uv run pytest tests/test_registry.py    # ✓ Works from anywhere
```

### Run specific tests

```bash
uv run pytest tests/test_integration.py::TestDevContainerStructure
uv run pytest tests/test_integration.py::TestDevContainerStructure::test_devcontainer_directory_exists
```

## Test Infrastructure

### Named Volumes for Docker-out-of-Docker

When running from inside a devcontainer, tests use **named volumes** instead of bind mounts. This solves the Docker-out-of-Docker path translation problem:

```bash
# Create a named volume
podman volume create test-workspace-XXXX

# Run with named volume (no host path needed!)
podman run -it --rm \
  -v test-workspace-XXXX:/workspace \
  ghcr.io/vig-os/devcontainer:dev \
  /root/assets/init-workspace.sh

# Copy files from volume to inspect results
podman run --rm \
  -v test-workspace-XXXX:/source:ro \
  -v /tmp/local:/dest \
  alpine cp -a /source/. /dest/
```

The `docker-compose.test.yml` file is provided for reference but tests use direct `podman` commands for broader compatibility.

### Container Detection

The test fixtures automatically detect if they're running inside a container by checking:

1. `IN_CONTAINER=true` environment variable
2. Presence of `/.dockerenv` or `/run/.containerenv`
3. `/proc/1/cgroup` contents

### Path Translation

When running from inside a container with `HOST_WORKSPACE_PATH` set, the `get_host_path()` function translates container paths to host paths for:

- Devcontainer CLI `--workspace-folder` arguments
- Volume mount paths in docker-compose.project.yaml
- Any operation that needs to communicate with the host's podman daemon

## Troubleshooting

### "no such file or directory" errors

If you see volume mount errors like:

```text
Error: statfs /workspace/devcontainer/tests/tmp/...:
no such file or directory
```

This means you're running from inside a container and the test is trying to use
a bind mount with a container path. The solution:

1. **For basic tests**: They should work automatically with the compose
   infrastructure
2. **For devcontainer CLI tests**: Set `HOST_WORKSPACE_PATH` environment
   variable

### Compose not found

If you get "command not found: podman compose":

```bash
# Check podman compose is available
podman compose version

# If not, it may be a separate package on your system
```

### Named volumes persist

Named volumes created during tests are automatically cleaned up. If you need to manually remove them:

```bash
# List volumes
podman volume ls | grep test-workspace

# Remove specific volume
podman volume rm test-workspace-XXXXXX

# Remove all test volumes
podman volume ls -q | grep test-workspace | xargs -r podman volume rm
```

## Architecture

```text
Host Machine
├── Devcontainer (you might be here)
│   ├── Tests run via pytest
│   │   ├── Use podman socket → Host's podman daemon
│   │   ├── Create named volumes (managed by compose)
│   │   └── Copy files from volumes to inspect results
│   │
│   └── For devcontainer CLI tests:
│       ├── Translate paths with HOST_WORKSPACE_PATH
│       └── CLI talks to host podman with host paths
│
└── Host Podman Daemon
    ├── Manages all containers (including test containers)
    ├── Manages named volumes
    └── Executes container operations
```

## Example: Running from Devcontainer

```bash
# 1. Open your devcontainer in VS Code or via CLI

# 2. For basic tests, just run them:
cd /workspace/devcontainer
make test-integration

# 3. For devcontainer CLI tests, set host path:
export HOST_WORKSPACE_PATH=/Users/yourname/Projects/devcontainer
make test-integration

# The tests will:
# - Detect they're in a container
# - Use compose with named volumes for init-workspace tests
# - Translate paths for devcontainer CLI tests
# - Clean up volumes automatically
```

## What Changed

Previously, tests used direct `podman run -v /container/path:/workspace` which
failed when running from inside a container (DooD) because the host couldn't
find `/container/path`.

Now, tests use:

- **Compose with named volumes** for workspace initialization
- **Path translation** for devcontainer CLI operations
- **Automatic detection** of container vs. host environment

This allows you to develop and test the devcontainer setup from within itself!
