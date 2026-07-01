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
    ruff check .

# Format code
[group('quality')]
format:
    ruff format .

# Run pre-commit hooks on all files
[group('quality')]
precommit:
    prek run --all-files

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
    echo "Image builder: Nix flake (.#devcontainerImage)"
    echo "Native arch: $NATIVE_ARCH"

# Gate Nix prerequisites and bootstrap the project (venv, git hooks, pre-commit)
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
    set -euo pipefail
    # Nix-only (#642): build the layered image from the flake and load it into
    # podman under the local `dev` tag. Builds natively for the host arch.
    # `no_cache` is accepted for compatibility but is a no-op — Nix builds are
    # content-addressed (there is no Docker layer cache to bust).
    echo "Building the Nix devcontainer image (.#devcontainerImage)..."
    nix build .#devcontainerImage --accept-flake-config --print-build-logs
    loaded=$(podman load -i result | sed -n 's/^Loaded image: //p' | head -n1)
    podman tag "${loaded}" "{{ repo }}:dev"
    echo "Loaded and tagged {{ repo }}:dev (from ${loaded})"

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
    # bats and its helper libraries come from the flake (the toolchain SSoT);
    # the wrapper exports BATS_LIB_PATH so test_helper.bash resolves them. #695.
    # Use GNU parallel if available for faster test execution
    if command -v parallel >/dev/null 2>&1; then
        echo "Running BATS tests in parallel..."
        find tests/bats -name '*.bats' -print0 | parallel -0 -j+0 bats {}
    else
        echo "Running BATS tests sequentially (install 'parallel' for faster execution)..."
        bats tests/bats/
    fi

# Validate tracked Renovate configs with renovate-config-validator --strict
[group('test')]
test-renovate:
    #!/usr/bin/env bash
    set -euo pipefail
    # Mirror .github/workflows/renovate-validate.yml: skip
    # assets/workspace/renovate.json because its preset is templated with the
    # repository name and only resolves after init copies it into a real repo.
    mapfile -t files < <(git ls-files 'renovate*.json' '**/renovate*.json' \
        | grep -vx 'assets/workspace/renovate.json' || true)
    if [ ${#files[@]} -eq 0 ]; then
        echo "No Renovate configs found."
        exit 0
    fi
    printf '%s\n' "${files[@]}"
    npx --yes --package renovate@latest -c "renovate-config-validator --strict ${files[*]}"

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
    @just test-renovate

# ===============================================================================
# RELEASE MANAGEMENT
# ===============================================================================
# Unified release via GitHub Actions (.github/workflows/release.yml, promote-release.yml)
#
# Process:
#   1. just prepare-release X.Y.Z    - Create release/X.Y.Z branch, draft PR
#   2. Test release branch, fix bugs as needed via PRs to release branch
#   3. Mark PR ready for review (gh pr ready PR_NUMBER)
#   4. Get PR approval from reviewer
#   5. just finalize-release X.Y.Z   - Triggers release.yml (final) that:
#      - Validates PR status and all prerequisites
#      - Sets release date in CHANGELOG, syncs PR docs
#      - Builds and tests container images; creates X.Y.Z tag; pushes versioned GHCR images
#      - Creates draft GitHub Release; dispatches smoke-test (not :latest yet)
#      - On failure: automatic rollback and issue creation
#   6. Wait for devcontainer-smoke-test to publish its final release for X.Y.Z
#   7. just promote-release X.Y.Z    - Triggers promote-release.yml that:
#      - Updates GHCR :latest, publishes the draft GitHub Release, merges release PR to main
#      - Merging to main triggers sync-main-to-dev.yml (PR main -> dev, auto-merge if clean)
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
    echo "Cleaning up lingering test containers..."
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
