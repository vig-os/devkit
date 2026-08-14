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

# Diagnostics only — always exits 0 (#1418; replaces the deleted
# TestHostGitSignatureSetup skip-on-failure tests).
# Diagnose host prerequisites: git identity, signing, hooks path, ssh-agent, gh auth
[group('info')]
doctor:
    #!/usr/bin/env bash
    echo "vigOS devkit doctor"
    echo "==================="

    name="$(git config user.name || true)"
    if [ -n "$name" ]; then
        echo "PASS git user.name: $name"
    else
        echo "WARN git user.name: not set (git config --global user.name ...)"
    fi

    email="$(git config user.email || true)"
    if [ -n "$email" ]; then
        echo "PASS git user.email: $email"
    else
        echo "WARN git user.email: not set (git config --global user.email ...)"
    fi

    gpgsign="$(git config commit.gpgsign || true)"
    format="$(git config gpg.format || true)"
    signingkey="$(git config user.signingkey || true)"
    if [ "$gpgsign" = "true" ] && [ -n "$signingkey" ] && \
        { [ "$format" != "ssh" ] || [ -r "$signingkey" ] || \
          [ "${signingkey#ssh-}" != "$signingkey" ]; }; then
        echo "PASS commit signing: $format key $signingkey"
    else
        echo "WARN commit signing: incomplete (commit.gpgsign=$gpgsign, gpg.format=$format, user.signingkey=$signingkey)"
    fi

    # .githooks is tracked, so a fresh clone has the shims on disk — but git
    # ignores them until core.hooksPath points there, and only scripts/init.sh
    # (or devcontainer / dev-shell entry) sets it. Until then every commit-side
    # gate is present, believed active, and inert. Refs #1430.
    #
    # A linked worktree may legitimately run with core.hooksPath unset and live
    # shims in the shared git dir (#1454). Since #1463 `just worktree-start`
    # leaves a configured hooks path untouched — the relative path resolves
    # against each worktree's root and .githooks is tracked, so a post-fix
    # worktree keeps the shared setting and hits the normal .githooks PASS
    # branch — and prek-installs into the shared .git/hooks only as the
    # fallback when no hooks path is configured at all. The shared-hooks PASS
    # branch below covers that fallback plus worktrees created before #1463
    # (worktree-start used to unset core.hooksPath — shared config, the #1463
    # bug — and always install): `hooks` is one of git's shared paths, so the
    # shims land in the common git dir and git runs them from inside the
    # worktree — the gates are live, and the fresh-clone remediation would undo
    # the setup. Claim that only when a shim is really installed and
    # executable: a worktree without one is inert exactly like any other unset
    # case. `--git-path hooks/pre-commit` resolves to the file git itself would
    # run (`.git` is a FILE in a linked worktree, so a literal `.git/hooks/...`
    # test could never see it).
    hookspath="$(git config core.hooksPath || true)"
    gitdir="$(git rev-parse --absolute-git-dir 2>/dev/null || true)"
    commondir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    installed="$(git rev-parse --git-path hooks/pre-commit 2>/dev/null || true)"
    if [ "$hookspath" = ".githooks" ]; then
        echo "PASS git hooks: core.hooksPath -> .githooks"
    elif [ -z "$hookspath" ] && [ -n "$gitdir" ] && [ "$gitdir" != "$commondir" ] && [ -x "$installed" ]; then
        echo "PASS git hooks: linked worktree, installed at $installed (core.hooksPath unset by design)"
    elif [ -z "$hookspath" ]; then
        echo "WARN git hooks: core.hooksPath not set, .githooks is tracked but inert (run: ./scripts/init.sh)"
    else
        echo "WARN git hooks: core.hooksPath=$hookspath, expected .githooks (run: ./scripts/init.sh)"
    fi

    if [ -n "${SSH_AUTH_SOCK:-}" ] && ssh-add -l >/dev/null 2>&1; then
        echo "PASS ssh-agent: reachable with $(ssh-add -l | wc -l) key(s)"
    else
        echo "WARN ssh-agent: not reachable or no keys loaded"
    fi

    if gh auth status >/dev/null 2>&1; then
        echo "PASS gh auth: logged in"
    else
        echo "WARN gh auth: not authenticated (run: gh auth login)"
    fi

    exit 0

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
    echo "Image builder: Nix flake (.#devkitImage)"
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
    echo "Building the Nix devcontainer image (.#devkitImage)..."
    nix build .#devkitImage --accept-flake-config --print-build-logs
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

# Run the vig-utils package test suite
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
#   3. just publish-candidate X.Y.Z  - Build/test/publish X.Y.Z-rcN to verify
#                                       (gates on CI only; PR may stay draft); repeat as needed
#   4. Mark PR ready for review (gh pr ready PR_NUMBER)
#   5. just finalize-release X.Y.Z   - Triggers release.yml (final) that:
#      - Validates PR status and all prerequisites (requires an RC published in step 3)
#      - Sets release date in CHANGELOG, syncs PR docs
#      - Builds and tests container images; creates X.Y.Z tag; pushes versioned GHCR images
#      - Creates draft GitHub Release; dispatches smoke-test (not :latest yet)
#      - On failure: automatic rollback and issue creation
#   6. Wait for devkit-smoke-test to publish its final release for X.Y.Z (unattended, #1506)
#   7. Approve the release PR (the cycle's single human approval, #1504) —
#      or reject with `just abandon-release X.Y.Z` (draft-only)
#   8. just promote-release X.Y.Z    - Triggers promote-release.yml that:
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
    if [ -n "$DEVCONTAINERS" ]; then
        echo "  Removing workspace devcontainers..."
        echo "$DEVCONTAINERS" | xargs -r podman rm -f
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
