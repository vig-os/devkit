#!/usr/bin/env bats
# BATS tests for install.sh
#
# These tests exercise install.sh flags and argument parsing without requiring
# a container runtime.  They complement the pytest-based unit tests in
# tests/test_utils.py::TestInstallScriptUnit.
#
# Test categories:
# - help flag (-h, --help)
# - option documentation
# - unknown option handling
# - dry-run mode
# - version flag
# - force flag
# - organization name flag
# - project name sanitization
# - invalid path handling
# - os detection
# - runtime detection
# - git repository setup

setup() {
    load test_helper
    INSTALL_SH="$PROJECT_ROOT/install.sh"
}

# ── help ──────────────────────────────────────────────────────────────────────

@test "help flag (-h) exits 0 and prints usage" {
    run bash "$INSTALL_SH" -h
    assert_success
    assert_output --partial "USAGE:"
    assert_output --partial "OPTIONS:"
}

@test "help flag (--help) exits 0 and prints usage" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "vigOS Devcontainer Install Script"
}

@test "help lists all documented options" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "--force"
    assert_output --partial "--version"
    assert_output --partial "--docker"
    assert_output --partial "--podman"
    assert_output --partial "--name"
    assert_output --partial "--org"
    assert_output --partial "--repo"
    assert_output --partial "--dry-run"
    assert_output --partial "--smoke-test"
}

# ── unknown option ────────────────────────────────────────────────────────────

@test "unknown option exits 1 with error" {
    run bash "$INSTALL_SH" --nonexistent
    assert_failure
    assert_output --partial "error"
    assert_output --partial "Unknown option"
}

# ── dry-run ───────────────────────────────────────────────────────────────────

@test "dry-run shows the command that would be executed" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "Would execute:"
    assert_output --partial "init-workspace.sh"
}

@test "dry-run command is derived from the CMD array via printf %q" {
    # The shown command must be rendered from the real CMD array, not a
    # hand-maintained duplicate string (#759).
    # shellcheck disable=SC2016
    run grep "printf '%q" "$INSTALL_SH"
    assert_success
}

@test "dry-run includes image registry in command" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer"
}

@test "dry-run output is shell-quoted for safe copy-paste" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    # The command is rendered from the real CMD array via printf '%q', so each
    # argument is shell-safe (quoted only when it contains special characters).
    assert_output --regexp '[^ ]+:/workspace'
    assert_output --regexp 'ghcr\.io/vig-os/devcontainer:[^ ]+'
}

# ── version flag ──────────────────────────────────────────────────────────────

@test "version flag appears in dry-run command" {
    run bash "$INSTALL_SH" --dry-run --version 1.2.3 .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer:1.2.3"
}

@test "default version is latest" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer:latest"
}

# ── force flag ────────────────────────────────────────────────────────────────

@test "force flag is forwarded to init-workspace.sh" {
    run bash "$INSTALL_SH" --dry-run --force .
    assert_success
    assert_output --partial "--force"
}

@test "smoke-test flag is forwarded to init-workspace.sh" {
    run bash "$INSTALL_SH" --dry-run --smoke-test .
    assert_success
    assert_output --partial "--smoke-test"
}

# ── org flag ──────────────────────────────────────────────────────────────────

@test "default org is vigOS" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial 'ORG_NAME=vigOS'
}

@test "default GITHUB_REPOSITORY is OWNER/REPO when no git origin" {
    local test_dir
    test_dir="$(mktemp -d)"
    run bash "$INSTALL_SH" --dry-run "$test_dir"
    assert_success
    assert_output --partial 'GITHUB_REPOSITORY=OWNER/REPO'
    rm -rf "$test_dir"
}

@test "custom --repo is passed to container" {
    run bash "$INSTALL_SH" --dry-run --repo vig-os/myapp .
    assert_success
    assert_output --partial 'GITHUB_REPOSITORY=vig-os/myapp'
}

@test "custom org is passed to container" {
    run bash "$INSTALL_SH" --dry-run --org MyOrg .
    assert_success
    assert_output --partial 'ORG_NAME=MyOrg'
}

# ── name flag / sanitization ─────────────────────────────────────────────────

@test "project name is sanitized in dry-run" {
    local test_dir
    test_dir="$(mktemp -d)"
    mkdir -p "$test_dir/My-Awesome-Project"

    run bash "$INSTALL_SH" --dry-run "$test_dir/My-Awesome-Project"
    assert_success
    assert_output --partial 'SHORT_NAME=my_awesome_project'

    rm -rf "$test_dir"
}

@test "custom name overrides directory name" {
    run bash "$INSTALL_SH" --dry-run --name custom_name .
    assert_success
    assert_output --partial 'SHORT_NAME=custom_name'
}

# ── invalid path ──────────────────────────────────────────────────────────────

@test "non-existent path exits 1" {
    run bash "$INSTALL_SH" --dry-run /tmp/nonexistent-path-$$
    assert_failure
    assert_output --partial "Directory does not exist"
}

# ── runtime detection ─────────────────────────────────────────────────────────

@test "install.sh includes detect_runtime function" {
    run grep 'detect_runtime()' "$INSTALL_SH"
    assert_success
}

@test "install.sh prefers podman over docker" {
    run grep 'command -v podman' "$INSTALL_SH"
    assert_success
}

@test "install.sh falls back to docker if podman unavailable" {
    run grep 'command -v docker' "$INSTALL_SH"
    assert_success
}

# ── os detection ──────────────────────────────────────────────────────────────

@test "install.sh includes detect_os function" {
    run grep 'detect_os()' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects macOS" {
    run grep 'Darwin\*' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Debian/Ubuntu" {
    run grep 'ubuntu|debian|pop|linuxmint' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Fedora/RHEL" {
    run grep 'fedora|rhel|centos|rocky|almalinux' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Arch Linux" {
    run grep 'arch|manjaro|endeavouros' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects openSUSE" {
    run grep 'opensuse\*|sles' "$INSTALL_SH"
    assert_success
}

# ── color output ──────────────────────────────────────────────────────────────

@test "install.sh uses colored output for interactive terminal" {
    run grep 'RED=' "$INSTALL_SH"
    assert_success
}

@test "install.sh disables colors for non-interactive terminal" {
    run grep 'if \[ -t 1 \]' "$INSTALL_SH"
    assert_success
}

# ── output functions ──────────────────────────────────────────────────────────

@test "install.sh defines err function for error messages" {
    run grep 'err() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines info function for info messages" {
    run grep 'info() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines warn function for warnings" {
    run grep 'warn() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines success function for success messages" {
    run grep 'success() {' "$INSTALL_SH"
    assert_success
}

# ── git repository setup (embedded in install.sh) ────────────────────────────

@test "install.sh includes setup_git_repo function" {
    run grep 'setup_git_repo()' "$INSTALL_SH"
    assert_success
}

@test "install.sh initializes git repo if missing" {
    run grep 'git init -b main' "$INSTALL_SH"
    assert_success
}

@test "install.sh creates initial commit if needed" {
    run grep 'git commit' "$INSTALL_SH"
    assert_success
}

@test "install.sh guards the scaffold commit against a populated directory" {
    # The automatic 'initial project scaffold' commit must only run for a
    # freshly scaffolded (empty) target, gated by the TARGET_WAS_EMPTY flag,
    # so it never sweeps a pre-populated directory into a misleading commit (#759).
    # shellcheck disable=SC2016
    run grep 'TARGET_WAS_EMPTY' "$INSTALL_SH"
    assert_success
}

@test "install.sh verifies main branch exists" {
    run grep 'git rev-parse --verify main' "$INSTALL_SH"
    assert_success
}

@test "install.sh verifies dev branch exists" {
    run grep 'git rev-parse --verify dev' "$INSTALL_SH"
    assert_success
}

@test "install.sh creates dev branch if missing" {
    run grep 'git branch dev' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows remote origin hint" {
    run grep 'git remote add origin' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows push hint" {
    run grep 'git push -u origin main dev' "$INSTALL_SH"
    assert_success
}

# ── user configuration ────────────────────────────────────────────────────────

@test "install.sh includes run_user_conf function" {
    run grep 'run_user_conf()' "$INSTALL_SH"
    assert_success
}

@test "install.sh looks for copy-host-user-conf.sh script" {
    run grep 'copy-host-user-conf.sh' "$INSTALL_SH"
    assert_success
}

# ── image pulling ─────────────────────────────────────────────────────────────

@test "install.sh pulls image before running" {
    run grep 'pull' "$INSTALL_SH"
    assert_success
}

@test "install.sh supports --skip-pull flag" {
    run grep 'SKIP_PULL' "$INSTALL_SH"
    assert_success
}

@test "install.sh checks local image with docker-compatible 'image inspect'" {
    # shellcheck disable=SC2016
    run grep '\$RUNTIME image inspect "\$IMAGE"' "$INSTALL_SH"
    assert_success
}

@test "install.sh does not use podman-only '\$RUNTIME image exists'" {
    # shellcheck disable=SC2016
    run grep '\$RUNTIME image exists' "$INSTALL_SH"
    assert_failure
}

# ── error handling ────────────────────────────────────────────────────────────

@test "install.sh validates container runtime availability" {
    run grep 'info' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows runtime installation instructions" {
    run grep 'show_install_instructions()' "$INSTALL_SH"
    assert_success
}

@test "install.sh requires interactive terminal" {
    run grep '\-t 0' "$INSTALL_SH"
    assert_success
}

# ── script structure ──────────────────────────────────────────────────────────

@test "install.sh uses strict error handling" {
    run grep 'set -euo pipefail' "$INSTALL_SH"
    assert_success
}

@test "install.sh is executable" {
    run test -x "$INSTALL_SH"
    assert_success
}

@test "install.sh has shebang" {
    run head -1 "$INSTALL_SH"
    assert_output "#!/usr/bin/env bash"
}

# ── .vig-os version-pin override (#852) ───────────────────────────────────────

@test "install.sh forwards --version to init-workspace as VIG_OS_VERSION (#852)" {
    # shellcheck disable=SC2016
    run grep -F 'VIG_OS_VERSION=$VERSION' "$INSTALL_SH"
    assert_success
}
