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

# ── linked worktrees: unset core.hooksPath can be a legitimate state (#1454) ──
# Since #1463 `just worktree-start` (justfile.worktree) leaves a configured
# core.hooksPath untouched — the tracked .githooks shims cover the worktree —
# and prek-installs only as the fallback when no hooks path is set at all. That
# fallback, plus worktrees created before #1463 (which always unset and
# installed), is why unset can still be live here.
# `hooks` is one of git's shared (common-dir) paths, so those
# shims land in the COMMON git dir and git runs them from inside the linked
# worktree: the gates are LIVE. Reporting the fresh-clone "tracked but inert"
# WARN there is a lie whose remediation would undo the worktree setup. A linked
# worktree with NO installed shim is genuinely inert and must stay a WARN.

# Run git for fixture setup with a pinned identity and no signing, so host
# global/system config can never make the fixture commit fail.
_git_fixture() {
    env GIT_CONFIG_GLOBAL="$GIT_GLOBAL" GIT_CONFIG_SYSTEM=/dev/null \
        git -c user.name=Fixture -c user.email=fixture@example.com \
            -c commit.gpgsign=false "$@"
}

# Build a real main clone + linked worktree under BATS_TEST_TMPDIR and point the
# run at the worktree. $1 = "hooks" to install an executable pre-commit shim
# where git looks with core.hooksPath unset (the common git dir — exactly where
# `prek install` lands from inside a linked worktree).
_init_linked_worktree() {
    _init_clone
    local main="$DOCTOR_WORK"
    _git_fixture -C "$main" commit -q --allow-empty -m "fixture"
    if [ "${1:-}" = "hooks" ]; then
        printf '#!/usr/bin/env bash\nexit 0\n' >"$main/.git/hooks/pre-commit"
        chmod +x "$main/.git/hooks/pre-commit"
    fi
    _git_fixture -C "$main" worktree add -q "$BATS_TEST_TMPDIR/linked" -b fixture/wt
    DOCTOR_WORK="$BATS_TEST_TMPDIR/linked"
}

@test "doctor reports PASS in a linked worktree with hooks installed" {
    _init_linked_worktree hooks
    _run_doctor
    assert_success
    assert_output --partial "PASS git hooks"
    assert_output --partial "linked worktree"
    refute_output --partial "WARN git hooks"
}

@test "doctor warns in a linked worktree with no hooks installed" {
    _init_linked_worktree
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "core.hooksPath not set"
    assert_output --partial "scripts/init.sh"
}

@test "doctor reports PASS in a linked worktree that still has core.hooksPath" {
    _init_linked_worktree
    git -C "$DOCTOR_WORK" config core.hooksPath .githooks
    _run_doctor
    assert_success
    assert_output --partial "PASS git hooks"
    refute_output --partial "WARN git hooks"
}

@test "doctor warns when the signing key path does not exist" {
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    git config --file "$GIT_GLOBAL" user.signingkey "$BATS_TEST_TMPDIR/missing.pub"
    _run_doctor
    assert_success
    assert_output --partial "WARN commit signing"
}

# git expands a leading `~/` itself when it consumes user.signingkey, so a
# tilde path is a working signing setup. `test -r` performs no such expansion
# (the shell only expands an unquoted literal `~`, never a variable's
# contents), so the readability guard used to fail and report a correctly
# configured host as incomplete. Refs #1546.
@test "doctor reports PASS for a tilde signing key path" {
    printf 'ssh-ed25519 AAAA test\n' >"$BATS_TEST_TMPDIR/key.pub"
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    # shellcheck disable=SC2088 # the literal, unexpanded tilde IS the fixture
    git config --file "$GIT_GLOBAL" user.signingkey '~/key.pub'
    _run_doctor HOME="$BATS_TEST_TMPDIR"
    assert_success
    assert_output --partial "PASS commit signing: ssh key ~/key.pub"
}

@test "doctor warns when a tilde signing key path does not exist" {
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    # shellcheck disable=SC2088 # the literal, unexpanded tilde IS the fixture
    git config --file "$GIT_GLOBAL" user.signingkey '~/missing.pub'
    _run_doctor HOME="$BATS_TEST_TMPDIR"
    assert_success
    assert_output --partial "WARN commit signing"
}
