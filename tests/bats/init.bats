#!/usr/bin/env bats
# shellcheck disable=SC2016
# BATS tests for init.sh
#
# init.sh is a Nix-first onboarding script: it gates on the host prerequisites
# (Nix + direnv) and the dev-shell toolchain, then performs one-time project
# bootstrap (uv sync, git hooks, commit template, pre-commit). The toolchain
# itself is provisioned by the flake (`flake.nix` devTools), NOT by this script.
#
# These tests verify:
# - Script structure and strict error handling
# - Flag parsing (--check, --no-direnv, --help)
# - The Nix/direnv prerequisite gate and dev-shell detection
# - The container short-circuit
# - That project bootstrap steps are wired up
# - That the legacy OS-detect / requirements.yaml installer is gone
#
# Note: SC2016 disabled because we intentionally use single quotes to search
# for literal shell syntax in the target script.

setup() {
    load test_helper
    INIT_SH="$PROJECT_ROOT/scripts/init.sh"
    BASH_BIN="$(command -v bash)"
}

# ── script structure ──────────────────────────────────────────────────────────

@test "init.sh is executable" {
    run test -x "$INIT_SH"
    assert_success
}

@test "init.sh has shebang" {
    run head -1 "$INIT_SH"
    assert_output "#!/usr/bin/env bash"
}

@test "init.sh uses strict error handling (set -euo pipefail)" {
    run grep 'set -euo pipefail' "$INIT_SH"
    assert_success
}

# ── flag parsing / help ─────────────────────────────────────────────────────────

@test "init.sh --help exits 0 and prints usage" {
    run bash "$INIT_SH" --help
    assert_success
    assert_output --partial "USAGE:"
}

@test "init.sh --help documents the --check flag" {
    run bash "$INIT_SH" --help
    assert_success
    assert_output --partial "--check"
}

@test "init.sh --help documents the --no-direnv flag" {
    run bash "$INIT_SH" --help
    assert_success
    assert_output --partial "--no-direnv"
}

@test "init.sh rejects unknown options" {
    run bash "$INIT_SH" --definitely-not-a-flag
    assert_failure
    assert_output --partial "Unknown option"
}

# ── nix-first prerequisite gate ─────────────────────────────────────────────────

@test "init.sh gates on Nix and points to the installer when absent" {
    # Empty PATH: `command -v nix` fails; the gate must fire before any external
    # tool is needed (pure shell builtins up to this point).
    local stub="$BATS_TEST_TMPDIR/empty-bin"
    mkdir -p "$stub"
    run env PATH="$stub" "$BASH_BIN" "$INIT_SH"
    assert_failure
    assert_output --partial "nixos.org/download"
}

@test "init.sh gate explains how to enable flakes + the vig-os cache" {
    local stub="$BATS_TEST_TMPDIR/empty-bin2"
    mkdir -p "$stub"
    run env PATH="$stub" "$BASH_BIN" "$INIT_SH"
    assert_failure
    assert_output --partial "experimental-features"
    assert_output --partial "vig-os.cachix.org"
}

@test "init.sh tells you to enter the dev shell when the toolchain is missing" {
    # nix present (stub), but the dev-shell toolchain (uv) is not on PATH.
    local stub="$BATS_TEST_TMPDIR/nix-only-bin"
    mkdir -p "$stub"
    ln -s "$(command -v true)" "$stub/nix"
    run env PATH="$stub" "$BASH_BIN" "$INIT_SH"
    assert_failure
    assert_output --partial "direnv allow"
}

# ── container short-circuit ─────────────────────────────────────────────────────

@test "init.sh is a no-op inside the built image (IN_CONTAINER=true)" {
    IN_CONTAINER=true run bash "$INIT_SH"
    assert_success
    assert_output --partial "already provisioned"
}

# ── check-only mode ─────────────────────────────────────────────────────────────

@test "init.sh --check verifies prerequisites without bootstrapping" {
    command -v nix >/dev/null || skip "nix not on PATH"
    command -v uv >/dev/null || skip "uv not on PATH"
    run bash "$INIT_SH" --check
    assert_success
    assert_output --partial "Prerequisites"
}

# ── project bootstrap is wired up ───────────────────────────────────────────────

@test "init.sh syncs the project venv from the lockfile" {
    run grep 'uv sync --frozen --all-extras' "$INIT_SH"
    assert_success
}

@test "init.sh configures the git hooks path" {
    run grep 'core.hooksPath .githooks' "$INIT_SH"
    assert_success
}

@test "init.sh configures the commit message template" {
    run grep 'commit.template .gitmessage' "$INIT_SH"
    assert_success
}

@test "init.sh installs pre-commit hooks" {
    run grep 'prek prepare-hooks' "$INIT_SH"
    assert_success
}

@test "init.sh probes the host container runtime (advisory)" {
    run grep 'podman info' "$INIT_SH"
    assert_success
}

@test "init.sh ensures a containers signature policy for podman load" {
    # `podman load` (just build) needs a policy.json that `podman info` does not;
    # the dev-shell podman ships none, so init must handle it.
    run grep 'policy.json' "$INIT_SH"
    assert_success
}

@test "init.sh writes the permissive containers policy default" {
    run grep 'insecureAcceptAnything' "$INIT_SH"
    assert_success
}

@test "init.sh checks the system containers policy before writing a user one" {
    # Idempotent / never-clobber: a system (or user) policy short-circuits the write.
    run grep -F '/etc/containers/policy.json' "$INIT_SH"
    assert_success
}

# ── legacy installer is gone ────────────────────────────────────────────────────

@test "requirements.yaml has been retired" {
    run test -f "$PROJECT_ROOT/scripts/requirements.yaml"
    assert_failure
}

@test "init.sh no longer references requirements.yaml" {
    run grep -F 'requirements.yaml' "$INIT_SH"
    assert_failure
}

@test "init.sh no longer detects the OS for package installs" {
    run grep -E 'detect_os|parse_requirements' "$INIT_SH"
    assert_failure
}

@test "init.sh no longer hardcodes a Python version" {
    run grep 'PYTHON_VERSION' "$INIT_SH"
    assert_failure
}

@test "init.sh no longer installs packages via apt/brew/dnf/apk" {
    run grep -E 'apt install|brew install|dnf install|apk add' "$INIT_SH"
    assert_failure
}

# ── output helpers retained ─────────────────────────────────────────────────────

@test "init.sh defines log_info helper" {
    run grep 'log_info()' "$INIT_SH"
    assert_success
}

@test "init.sh defines log_error helper" {
    run grep 'log_error()' "$INIT_SH"
    assert_success
}

# ── devcontainer CLI check (conftest, unrelated to package installs) ─────────────

@test "conftest.py devcontainer check falls back to node_modules/.bin" {
    run grep 'node_modules/.bin/devcontainer' "$PROJECT_ROOT/tests/conftest.py"
    assert_success
}

@test "conftest.py devcontainer skip message does not reference npm install -g" {
    run grep 'npm install -g.*devcontainer' "$PROJECT_ROOT/tests/conftest.py"
    assert_failure
}
