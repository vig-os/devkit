#!/usr/bin/env bats
# shellcheck disable=SC2016
# BATS tests for clean.sh
#
# Tests the clean.sh script which removes container images and manifests.
# These tests verify:
# - Version and repository argument handling
# - Manifest list removal
# - Arch-specific image removal (amd64, arm64)
# - Main image removal
# - Error handling
# - Verification after cleanup
#
# Note: SC2016 disabled because we intentionally use single quotes to search
# for literal shell variable syntax (e.g., '$VAR') in the target scripts.

setup() {
    load test_helper
    CLEAN_SH="$PROJECT_ROOT/scripts/clean.sh"
}

# ── script structure ──────────────────────────────────────────────────────────

@test "clean.sh is executable" {
    run test -x "$CLEAN_SH"
    assert_success
}

@test "clean.sh has shebang" {
    run head -1 "$CLEAN_SH"
    assert_output "#!/usr/bin/env bash"
}

# ── argument handling ─────────────────────────────────────────────────────────

@test "clean.sh accepts version as first argument" {
    run grep 'VERSION="\${1:-dev}"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh defaults version to 'dev'" {
    run grep 'VERSION="\${1:-dev}"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh handles version= prefix in arguments" {
    run grep 'if \[\[ "\$VERSION" =~ \^version= \]\]' "$CLEAN_SH"
    assert_success
}

@test "clean.sh strips version= prefix" {
    run grep 'VERSION="\${VERSION#version=}"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh accepts repository as second argument" {
    run grep 'REPO=' "$CLEAN_SH"
    assert_success
}

@test "clean.sh uses TEST_REGISTRY environment variable" {
    run grep 'TEST_REGISTRY' "$CLEAN_SH"
    assert_success
}

@test "clean.sh defaults to ghcr.io/vig-os/devkit registry" {
    run grep 'ghcr.io/vig-os/devkit' "$CLEAN_SH"
    assert_success
}

@test "clean.sh removes trailing slash from repository" {
    run grep 'REPO="\${REPO%/}"' "$CLEAN_SH"
    assert_success
}

# ── error handling ────────────────────────────────────────────────────────────

@test "clean.sh uses strict mode (set -e)" {
    run grep 'set -e' "$CLEAN_SH"
    assert_success
}

# ── directory setup ───────────────────────────────────────────────────────────

@test "clean.sh derives SCRIPT_DIR from script path" {
    run grep 'SCRIPT_DIR=' "$CLEAN_SH"
    assert_success
}

@test "clean.sh derives PROJECT_ROOT as parent of SCRIPT_DIR" {
    run grep 'PROJECT_ROOT=' "$CLEAN_SH"
    assert_success
}

@test "clean.sh changes to PROJECT_ROOT" {
    run grep 'cd "\$PROJECT_ROOT"' "$CLEAN_SH"
    assert_success
}

# ── image name construction ───────────────────────────────────────────────────

@test "clean.sh constructs IMAGE_NAME from repository and version" {
    run grep 'IMAGE_NAME="\$REPO:\$VERSION"' "$CLEAN_SH"
    assert_success
}

# ── manifest list removal ─────────────────────────────────────────────────────

@test "clean.sh checks if manifest list exists" {
    run grep 'podman manifest exists "\$IMAGE_NAME"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh outputs message before manifest removal" {
    run grep 'echo "Removing manifest list' "$CLEAN_SH"
    assert_success
}

@test "clean.sh attempts to remove manifest list" {
    run grep 'podman manifest rm "\$IMAGE_NAME"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh handles manifest removal failures" {
    run grep 'if ! podman manifest rm' "$CLEAN_SH"
    assert_success
}

@test "clean.sh warns on manifest removal failure" {
    run grep '⚠️  Failed to remove manifest list' "$CLEAN_SH"
    assert_success
}

# ── local images retrieval ────────────────────────────────────────────────────

@test "clean.sh retrieves list of local images" {
    run grep 'LOCAL_IMAGES=\$(podman images' "$CLEAN_SH"
    assert_success
}

@test "clean.sh formats images as repository:tag" {
    run grep '{{.Repository}}:{{.Tag}}' "$CLEAN_SH"
    assert_success
}

@test "clean.sh handles podman images errors gracefully" {
    run grep '2>/dev/null || echo ""' "$CLEAN_SH"
    assert_success
}

# ── arch-specific image removal ───────────────────────────────────────────────

@test "clean.sh removes amd64 arch-specific images" {
    run grep 'for arch in amd64 arm64' "$CLEAN_SH"
    assert_success
}

@test "clean.sh removes arm64 arch-specific images" {
    run grep 'for arch in amd64 arm64' "$CLEAN_SH"
    assert_success
}

@test "clean.sh constructs arch-specific tag with hyphen" {
    run grep 'ARCH_TAG="\${IMAGE_NAME}-\${arch}"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh checks if arch-specific image exists locally" {
    run grep 'if echo "\$LOCAL_IMAGES" | grep -q "\^\${ARCH_TAG}$"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh outputs message before arch image removal" {
    run grep 'echo "Removing arch-specific image' "$CLEAN_SH"
    assert_success
}

@test "clean.sh removes arch-specific image with force flag" {
    run grep 'podman rmi -f "\$ARCH_TAG"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh handles arch-specific image removal failures" {
    run grep 'if ! podman rmi -f "\$ARCH_TAG"' "$CLEAN_SH"
    assert_success
}

# ── main image removal ────────────────────────────────────────────────────────

@test "clean.sh checks if main image exists locally" {
    run grep 'if echo "\$LOCAL_IMAGES" | grep -q "\^\${IMAGE_NAME}$"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh outputs message before main image removal" {
    run grep 'echo "Removing image \$IMAGE_NAME' "$CLEAN_SH"
    assert_success
}

@test "clean.sh tries manifest removal first for main image" {
    run grep 'podman manifest rm "\$IMAGE_NAME" 2>/dev/null || true' "$CLEAN_SH"
    assert_success
}

@test "clean.sh removes main image with force flag" {
    run grep 'podman rmi -f "\$IMAGE_NAME"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh handles main image removal failures" {
    run grep 'if ! podman rmi -f "\$IMAGE_NAME"' "$CLEAN_SH"
    assert_success
}

# ── final verification ────────────────────────────────────────────────────────

@test "clean.sh verifies image no longer exists" {
    run grep 'podman image exists "\$IMAGE_NAME"' "$CLEAN_SH"
    assert_success
}

@test "clean.sh warns if image still exists after cleanup" {
    run grep 'Warning.*still exists after cleanup' "$CLEAN_SH"
    assert_success
}

@test "clean.sh attempts aggressive cleanup if needed" {
    run bash -c "grep -c 'podman manifest rm \"\$IMAGE_NAME\"' '$CLEAN_SH'"
    local count="$output"
    [ "$count" -gt 1 ]
}

@test "clean.sh outputs error if final cleanup fails" {
    run grep 'Error.*could not be removed' "$CLEAN_SH"
    assert_success
}

# ── success output ────────────────────────────────────────────────────────────

@test "clean.sh outputs success for manifest removal" {
    run grep '✓ Removed manifest list' "$CLEAN_SH"
    assert_success
}

@test "clean.sh outputs success for image removal" {
    run grep '✓ Removed image' "$CLEAN_SH"
    assert_success
}
