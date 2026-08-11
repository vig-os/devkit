#!/usr/bin/env bats
# BATS tests for clean.sh
#
# Behavioral tests: clean.sh runs for real against a logging `podman` stub on
# PATH (same pattern as install.bats' stub runtimes), so every test proves what
# the script *does* — argument handling, removal ordering, error paths, final
# verification — instead of grepping its source. The stub records each podman
# invocation to a log and answers according to STUB_* environment knobs:
#   STUB_MANIFEST_EXISTS_RC  exit code for `podman manifest exists` (default 1)
#   STUB_MANIFEST_RM_RC      exit code for `podman manifest rm`     (default 0)
#   STUB_IMAGE_EXISTS_RC     exit code for `podman image exists`    (default 1)
#   STUB_IMAGES_RC           exit code for `podman images`          (default 0)
#   STUB_LOCAL_IMAGES        newline-separated `repo:tag` list to print
#   STUB_RMI_RC              exit code for `podman rmi`             (default 0)
# The script is invoked directly (not via `bash`), so the executable bit and
# shebang are exercised on every run.

setup() {
    load test_helper
    CLEAN_SH="$PROJECT_ROOT/scripts/clean.sh"
    STUB_DIR="$BATS_TEST_TMPDIR/stub-bin"
    STUB_LOG="$BATS_TEST_TMPDIR/podman.log"
    mkdir -p "$STUB_DIR"
    cat >"$STUB_DIR/podman" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$STUB_LOG"
case "$1 $2" in
"manifest exists") exit "${STUB_MANIFEST_EXISTS_RC:-1}" ;;
"manifest rm")     exit "${STUB_MANIFEST_RM_RC:-0}" ;;
"image exists")    exit "${STUB_IMAGE_EXISTS_RC:-1}" ;;
esac
case "$1" in
images)
    [ "${STUB_IMAGES_RC:-0}" -eq 0 ] || exit "${STUB_IMAGES_RC}"
    if [ -n "${STUB_LOCAL_IMAGES:-}" ]; then
        printf '%s\n' "$STUB_LOCAL_IMAGES"
    fi
    exit 0
    ;;
rmi) exit "${STUB_RMI_RC:-0}" ;;
esac
exit 0
STUB
    chmod +x "$STUB_DIR/podman"
}

# Run clean.sh with the stub podman on PATH. Extra VAR=value words are passed
# into the environment; script arguments follow a literal `--`.
_run_clean() {
    local envs=()
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do
        envs+=("$1")
        shift
    done
    [ "${1:-}" = "--" ] && shift
    run env PATH="$STUB_DIR:$PATH" STUB_LOG="$STUB_LOG" TEST_REGISTRY= \
        "${envs[@]}" "$CLEAN_SH" "$@"
}

@test "clean.sh defaults version to dev and removes manifest, arch images, then the main tag in order" {
    _run_clean \
        STUB_MANIFEST_EXISTS_RC=0 \
        STUB_LOCAL_IMAGES=$'ghcr.io/vig-os/devcontainer:dev\nghcr.io/vig-os/devcontainer:dev-amd64\nghcr.io/vig-os/devcontainer:dev-arm64' \
        --
    assert_success
    assert_output --partial "✓ Removed manifest list ghcr.io/vig-os/devcontainer:dev"
    assert_output --partial "✓ Removed image ghcr.io/vig-os/devcontainer:dev"
    expected="$BATS_TEST_TMPDIR/expected.log"
    printf '%s\n' \
        "manifest exists ghcr.io/vig-os/devcontainer:dev" \
        "manifest rm ghcr.io/vig-os/devcontainer:dev" \
        "images --format {{.Repository}}:{{.Tag}}" \
        "rmi -f ghcr.io/vig-os/devcontainer:dev-amd64" \
        "rmi -f ghcr.io/vig-os/devcontainer:dev-arm64" \
        "manifest rm ghcr.io/vig-os/devcontainer:dev" \
        "rmi -f ghcr.io/vig-os/devcontainer:dev" \
        "image exists ghcr.io/vig-os/devcontainer:dev" \
        >"$expected"
    run diff "$expected" "$STUB_LOG"
    assert_success
}

@test "clean.sh strips the version= prefix that just passes through" {
    _run_clean \
        STUB_LOCAL_IMAGES='ghcr.io/vig-os/devcontainer:1.2.3' \
        -- version=1.2.3
    assert_success
    run grep -Fx "rmi -f ghcr.io/vig-os/devcontainer:1.2.3" "$STUB_LOG"
    assert_success
}

@test "clean.sh accepts a repository argument and strips its trailing slash" {
    _run_clean -- dev "example.com/org/img/"
    assert_success
    run grep -Fx "manifest exists example.com/org/img:dev" "$STUB_LOG"
    assert_success
}

@test "clean.sh takes the default repository from TEST_REGISTRY" {
    _run_clean TEST_REGISTRY="registry.example/mirror" --
    assert_success
    run grep -Fx "manifest exists registry.example/mirror:dev" "$STUB_LOG"
    assert_success
}

@test "clean.sh warns and fails when the manifest list cannot be removed" {
    _run_clean STUB_MANIFEST_EXISTS_RC=0 STUB_MANIFEST_RM_RC=1 --
    assert_failure
    assert_output --partial "Failed to remove manifest list ghcr.io/vig-os/devcontainer:dev"
}

@test "clean.sh warns and fails when an arch-specific image cannot be removed" {
    _run_clean \
        STUB_LOCAL_IMAGES='ghcr.io/vig-os/devcontainer:dev-amd64' \
        STUB_RMI_RC=1 \
        --
    assert_failure
    assert_output --partial "Failed to remove ghcr.io/vig-os/devcontainer:dev-amd64"
}

@test "clean.sh removes nothing and succeeds when no local image matches, even if podman images errors" {
    _run_clean STUB_IMAGES_RC=1 --
    assert_success
    run grep -E '^(rmi|manifest rm)' "$STUB_LOG"
    assert_failure
}

@test "clean.sh retries aggressively when the image survives cleanup, then errors" {
    _run_clean STUB_IMAGE_EXISTS_RC=0 --
    assert_failure
    assert_output --partial "still exists after cleanup"
    assert_output --partial "could not be removed"
    # The aggressive retry runs manifest rm + rmi -f between the two
    # `image exists` probes.
    run grep -c "^image exists " "$STUB_LOG"
    assert_output "2"
    run grep -Fx "manifest rm ghcr.io/vig-os/devcontainer:dev" "$STUB_LOG"
    assert_success
    run grep -Fx "rmi -f ghcr.io/vig-os/devcontainer:dev" "$STUB_LOG"
    assert_success
}
