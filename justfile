# ===============================================================================
# vigOS Devcontainer - Just Recipes
# Build automation for devcontainer image development
# ===============================================================================
# ===============================================================================
# VARIABLES
# ===============================================================================
# Allow TEST_REGISTRY to override REPO for testing (e.g., localhost:5000/test/)

repo := env("TEST_REGISTRY", "ghcr.io/vig-os/devcontainer")

# ===============================================================================
# INFO
# ===============================================================================

# Show available commands (default)
[group('info')]
default:
    @just --list --unsorted

# Show available commands
[group('info')]
help:
    @just --list

# ===============================================================================
# CODE QUALITY
# ===============================================================================

# Run all linters
[group('quality')]
lint:
    uv run ruff check .

# Format code
[group('quality')]
format:
    uv run ruff format .

# Run pre-commit hooks on all files
[group('quality')]
precommit:
    uv run pre-commit run --all-files

# Show image information
[group('info')]
info:
    #!/usr/bin/env bash
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
        NATIVE_ARCH="linux/arm64"
    else
        NATIVE_ARCH="linux/amd64"
    fi
    echo "Image: {{ repo }}"
    echo "Containerfile: Containerfile"
    echo "Native arch: $NATIVE_ARCH"

# Install system dependencies and setup development environment
[group('info')]
init *args:
    ./scripts/init.sh {{ args }}

# Generate documentation from templates
[group('info')]
docs:
    uv run python docs/generate.py

# Sync workspace templates from repo root to assets/workspace/
[group('info')]
sync-workspace:
    uv run python scripts/sync_manifest.py sync assets/workspace/

# Test login to GHCR
[group('info')]
login:
    #!/usr/bin/env bash
    echo "Logging in to GitHub Container Registry..."
    podman login ghcr.io

# ===============================================================================
# BUILD
# ===============================================================================

# Build local development image
[group('build')]
build no_cache="":
    #!/usr/bin/env bash
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
        NATIVE_ARCH="linux/arm64"
    else
        NATIVE_ARCH="linux/amd64"
    fi
    if [ -n "{{ no_cache }}" ]; then
        ./scripts/build.sh --no-cache dev "{{ repo }}" "$NATIVE_ARCH"
    else
        ./scripts/build.sh dev "{{ repo }}" "$NATIVE_ARCH"
    fi

# ===============================================================================
# TEST
# ===============================================================================

# Helper to ensure dev image exists before running image/integration tests
[private]
_ensure-dev-image version="dev":
    #!/usr/bin/env bash
    if ! podman image exists "{{ repo }}:{{ version }}"; then
        if [ "{{ version }}" = "dev" ]; then
            echo "Building dev image..."
            just build
        else
            echo "[ERROR] Image {{ repo }}:{{ version }} not found. Please build it first."
            exit 1
        fi
    fi

# Run image tests only
[group('test')]
test-image version="dev":
    @just _ensure-dev-image {{ version }}
    #!/usr/bin/env bash
    TEST_CONTAINER_TAG={{ version }} uv run pytest tests/test_image.py -v --tb=short

# Run integration tests only
[group('test')]
test-integration version="dev":
    @just _ensure-dev-image {{ version }}
    #!/usr/bin/env bash
    TEST_CONTAINER_TAG={{ version }} uv run pytest tests/test_integration.py -v --tb=short

# Run utils tests only
[group('test')]
test-utils:
    #!/usr/bin/env bash
    uv run pytest tests/test_utils.py -v -s --tb=short

# Run install script tests only
[group('test')]
test-install:
    #!/usr/bin/env bash
    uv run pytest tests/test_install_script.py -v -s --tb=short

# Run validate commit msg tests only
[group('test')]
test-validate-commit-msg:
    #!/usr/bin/env bash
    uv run pytest tests/test_validate_commit_msg.py -v -s --tb=short

# Run check action pins tests only
[group('test')]
test-vig-utils:
    #!/usr/bin/env bash
    uv run pytest packages/vig-utils/tests -v -s --tb=short

# Run BATS shell script tests
[group('test')]
test-bats:
    #!/usr/bin/env bash
    # Use GNU parallel if available for faster test execution
    if command -v parallel >/dev/null 2>&1; then
        echo "Running BATS tests in parallel..."
        find tests/bats -name '*.bats' -print0 | parallel -0 -j+0 npx bats {}
    else
        echo "Running BATS tests sequentially (install 'parallel' for faster execution)..."
        npx bats tests/bats/
    fi

# Clean up lingering containers before running tests
[private]
_test-cleanup-check:
    #!/usr/bin/env bash
    if podman ps -a --filter "name=workspace-devcontainer" -q 2>/dev/null | grep -q .; then
        echo "[!]  Lingering test containers found, cleaning up..."
        just clean-test-containers
    fi

# Run all test suites
[group('test')]
test version="dev":
    @just _test-cleanup-check
    @just _ensure-dev-image {{ version }}
    #!/usr/bin/env bash
    TEST_CONTAINER_TAG={{ version }}  uv run pytest tests -v -s --tb=short
    @just test-bats

# ===============================================================================
# RELEASE MANAGEMENT
# ===============================================================================
# Unified release workflow via GitHub Actions (.github/workflows/release.yml)
#
# Process:
#   1. just prepare-release X.Y.Z    - Create release/X.Y.Z branch, draft PR
#   2. Test release branch, fix bugs as needed via PRs to release branch
#   3. Mark PR ready for review (gh pr ready PR_NUMBER)
#   4. Get PR approval from reviewer
#   5. just finalize-release X.Y.Z   - Triggers GitHub Actions workflow that:
#      - Validates PR status and all prerequisites
#      - Sets release date in CHANGELOG, syncs PR docs
#      - Builds and tests container images
#      - Creates vX.Y.Z tag
#      - Publishes images to GHCR
#      - On failure: automatic rollback and issue creation
#   6. Merge release PR to main       - Triggers sync-main-to-dev.yml automatically:
#      - Opens PR to merge main into dev
#      - Auto-merges if no conflicts
# ===============================================================================
# ===============================================================================
# BUILD / CLEAN
# ===============================================================================

# Remove image (default: dev)
[group('build')]
clean version="dev":
    #!/usr/bin/env bash
    # Use TEST_REGISTRY from environment if set, otherwise use repo variable
    # This allows tests to override the repo via TEST_REGISTRY at runtime
    export TEST_REGISTRY
    REPO="${TEST_REGISTRY:-{{ repo }}}"
    # If TEST_REGISTRY was used and doesn't contain a path, append /test
    # This handles cases where TEST_REGISTRY=localhost:PORT instead of localhost:PORT/test
    if [[ -n "$TEST_REGISTRY" && "$REPO" == "$TEST_REGISTRY" && "$REPO" != *"/"* ]]; then
        REPO="${REPO}/test"
    fi
    ./scripts/clean.sh "{{ version }}" "$REPO"

# Clean up lingering test containers
[group('build')]
clean-test-containers:
    #!/usr/bin/env bash
    echo "Cleaning Cleaning up lingering test containers..."
    FMT=$(printf '\x7b\x7b.ID\x7d\x7d')
    DEVCONTAINERS=$(podman ps -a --filter "name=workspace-devcontainer" --format "$FMT" 2>/dev/null)
    SIDECARS=$(podman ps -a --filter "name=test-sidecar" --format "$FMT" 2>/dev/null)
    if [ -n "$DEVCONTAINERS" ] || [ -n "$SIDECARS" ]; then
        if [ -n "$DEVCONTAINERS" ]; then
            echo "  Removing workspace devcontainers..."
            echo "$DEVCONTAINERS" | xargs -r podman rm -f
        fi
        if [ -n "$SIDECARS" ]; then
            echo "  Removing test sidecars..."
            echo "$SIDECARS" | xargs -r podman rm -f
        fi
        echo "[OK] Cleanup complete"
    else
        echo "[*] No lingering test containers found"
    fi

# ===============================================================================
# PODMAN
# ===============================================================================
# Podman container & image management recipes

import 'justfile.podman'
import 'justfile.gh'
import 'justfile.worktree'
