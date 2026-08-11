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
    run env PATH="$DOCTOR_STUBS:$PATH" \
        GIT_CONFIG_GLOBAL="$GIT_GLOBAL" GIT_CONFIG_SYSTEM=/dev/null \
        -u SSH_AUTH_SOCK "$@" \
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

@test "doctor warns when the signing key path does not exist" {
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    git config --file "$GIT_GLOBAL" user.signingkey "$BATS_TEST_TMPDIR/missing.pub"
    _run_doctor
    assert_success
    assert_output --partial "WARN commit signing"
}
