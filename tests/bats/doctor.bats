#!/usr/bin/env bats
# BATS tests for the `just doctor` host-diagnostics recipe (#1418).
#
# `doctor` replaces the deleted TestHostGitSignatureSetup pytest class: instead
# of tests that skip on the failures they were meant to catch, host
# prerequisites (git identity, commit signing, ssh-agent, gh auth) are reported
# as PASS/WARN diagnostic lines. Diagnostics are not a gate: the recipe always
# exits 0. Tests drive the recipe under a controlled environment
# (GIT_CONFIG_GLOBAL/SYSTEM, SSH_AUTH_SOCK, stub `gh`) so host state never
# leaks in.

setup() {
    load test_helper
    DOCTOR_WORK="$BATS_TEST_TMPDIR/host"
    DOCTOR_STUBS="$BATS_TEST_TMPDIR/doctor-stubs"
    GIT_GLOBAL="$BATS_TEST_TMPDIR/gitconfig"
    mkdir -p "$DOCTOR_WORK" "$DOCTOR_STUBS"
    : >"$GIT_GLOBAL"
    # Stub gh: GH_STUB_RC controls `gh auth status` (default: not logged in).
    cat >"$DOCTOR_STUBS/gh" <<'STUB'
#!/usr/bin/env bash
if [ "${GH_STUB_RC:-1}" -eq 0 ]; then
    echo "Logged in to github.com"
fi
exit "${GH_STUB_RC:-1}"
STUB
    chmod +x "$DOCTOR_STUBS/gh"
}

_run_doctor() {
    run env -u SSH_AUTH_SOCK PATH="$DOCTOR_STUBS:$PATH" \
        GIT_CONFIG_GLOBAL="$GIT_GLOBAL" GIT_CONFIG_SYSTEM=/dev/null "$@" \
        just --justfile "$PROJECT_ROOT/justfile" \
        --working-directory "$DOCTOR_WORK" doctor
}

@test "doctor always exits 0 and warns on an unconfigured host" {
    _run_doctor
    assert_success
    assert_output --partial "devkit doctor"
    assert_output --partial "WARN git user.name"
    assert_output --partial "WARN git user.email"
    assert_output --partial "WARN commit signing"
    assert_output --partial "WARN ssh-agent"
    assert_output --partial "WARN gh auth"
}

@test "doctor reports PASS for configured git identity and signing" {
    git config --file "$GIT_GLOBAL" user.name "Test User"
    git config --file "$GIT_GLOBAL" user.email "test@example.com"
    git config --file "$GIT_GLOBAL" gpg.format ssh
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" user.signingkey "$BATS_TEST_TMPDIR/key.pub"
    printf 'ssh-ed25519 AAAA test\n' >"$BATS_TEST_TMPDIR/key.pub"
    _run_doctor GH_STUB_RC=0
    assert_success
    assert_output --partial "PASS git user.name: Test User"
    assert_output --partial "PASS git user.email: test@example.com"
    assert_output --partial "PASS commit signing"
    assert_output --partial "PASS gh auth"
}

# Make DOCTOR_WORK a real repository so `git config core.hooksPath` resolves
# against a known local config and can never walk up into the host's checkout
# (the run already pins GIT_CONFIG_GLOBAL/SYSTEM, so global state cannot leak
# either). This is the shape of the case #1430 reports: a fresh clone that has
# .githooks on disk but no core.hooksPath pointing at it.
_init_clone() {
    git -c init.defaultBranch=main init -q "$DOCTOR_WORK"
}

@test "doctor warns when core.hooksPath is unset in a fresh clone" {
    _init_clone
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "core.hooksPath not set"
    assert_output --partial "scripts/init.sh"
}

@test "doctor reports PASS when core.hooksPath points at .githooks" {
    _init_clone
    git -C "$DOCTOR_WORK" config core.hooksPath .githooks
    _run_doctor
    assert_success
    assert_output --partial "PASS git hooks"
    refute_output --partial "WARN git hooks"
}

@test "doctor warns and names the value when core.hooksPath points elsewhere" {
    _init_clone
    git -C "$DOCTOR_WORK" config core.hooksPath .git/hooks
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "core.hooksPath=.git/hooks"
    assert_output --partial "scripts/init.sh"
}

@test "doctor warns when the signing key path does not exist" {
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    git config --file "$GIT_GLOBAL" user.signingkey "$BATS_TEST_TMPDIR/missing.pub"
    _run_doctor
    assert_success
    assert_output --partial "WARN commit signing"
}
