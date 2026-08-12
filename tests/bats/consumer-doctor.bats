#!/usr/bin/env bats
# BATS tests for the SCAFFOLDED `just doctor` host-diagnostics recipe (#1448).
#
# `doctor` shipped in devkit's own justfile only (#1418, extended in #1430), so
# a consumer clone got no host preflight at all — the population where the
# "configured, believed active, never executed" hooks failure hurts most. This
# ships the same diagnostic on the consumer surface, in the MANAGED root
# justfile (assets/workspace/justfile): it is the only managed justfile layer
# present in every delivery mode (direnv/bare carry no .devcontainer/), and
# justfile.project is preserved on upgrade so a recipe placed there would never
# reach an existing consumer.
#
# The remediation hint is where the two implementations legitimately differ:
# devkit's points at ./scripts/init.sh, which a consumer does not have. A
# consumer's core.hooksPath is wired by the devcontainer setup
# (setup-git-conf.sh) or on dev-shell entry (githooksPathHook, #1112), so the
# hint names the mode's entry point from `.vig-os` DEVKIT_MODE, on top of a
# universal `git config core.hooksPath .githooks` that works in every mode
# (including `bare`, where nothing wires it automatically).
#
# Tests drive the REAL shipped justfile in a fixture workspace under a
# controlled environment (GIT_CONFIG_GLOBAL/SYSTEM, SSH_AUTH_SOCK, stub `gh`)
# so host state never leaks in — same harness idiom as doctor.bats.

setup() {
    load test_helper
    WS="$BATS_TEST_TMPDIR/ws"
    STUBS="$BATS_TEST_TMPDIR/stubs"
    GIT_GLOBAL="$BATS_TEST_TMPDIR/gitconfig"
    mkdir -p "$WS" "$STUBS"
    : >"$GIT_GLOBAL"
    # The managed root justfile, exactly as scaffolded into a consumer repo.
    cp "$PROJECT_ROOT/assets/workspace/justfile" "$WS/justfile"
    # Stub gh: GH_STUB_RC controls `gh auth status` (default: not logged in).
    cat >"$STUBS/gh" <<'STUB'
#!/usr/bin/env bash
if [ "${GH_STUB_RC:-1}" -eq 0 ]; then
    echo "Logged in to github.com"
fi
exit "${GH_STUB_RC:-1}"
STUB
    chmod +x "$STUBS/gh"
}

# Make the fixture a real repository so `git config core.hooksPath` resolves
# against a known local config and can never walk up into the host's checkout
# (the run also pins GIT_CONFIG_GLOBAL/SYSTEM, so global state cannot leak).
# Shape of a scaffolded clone: tracked .githooks on disk, `.vig-os` manifest.
# $1 (optional) is the DEVKIT_MODE value; omit it for a mode-less manifest.
_scaffold_repo() {
    git -c init.defaultBranch=main init -q "$WS"
    mkdir -p "$WS/.githooks"
    printf '#!/usr/bin/env bash\n' >"$WS/.githooks/pre-commit"
    printf 'DEVKIT_VERSION=1.8.0\n' >"$WS/.vig-os"
    if [ "$#" -gt 0 ]; then
        printf 'DEVKIT_MODE=%s\n' "$1" >>"$WS/.vig-os"
    fi
}

_run_doctor() {
    run env -u SSH_AUTH_SOCK PATH="$STUBS:$PATH" \
        GIT_CONFIG_GLOBAL="$GIT_GLOBAL" GIT_CONFIG_SYSTEM=/dev/null "$@" \
        just --justfile "$WS/justfile" --working-directory "$WS" doctor
}

# ── layering: the recipe must ship in the MANAGED layer ───────────────────────

@test "doctor ships in the managed root justfile, not the preserved justfile.project" {
    run grep -qE '^doctor:' "$PROJECT_ROOT/assets/workspace/justfile"
    assert_success
    run grep -qE '^doctor:' "$PROJECT_ROOT/assets/workspace/justfile.project"
    assert_failure
}

# ── diagnostics, never a gate ─────────────────────────────────────────────────

@test "consumer doctor always exits 0 and warns on an unconfigured host" {
    _scaffold_repo
    _run_doctor
    assert_success
    assert_output --partial "devkit doctor"
    assert_output --partial "WARN git user.name"
    assert_output --partial "WARN git user.email"
    assert_output --partial "WARN commit signing"
    assert_output --partial "WARN git hooks"
    assert_output --partial "WARN ssh-agent"
    assert_output --partial "WARN gh auth"
}

@test "consumer doctor reports PASS for configured git identity and signing" {
    _scaffold_repo
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

@test "consumer doctor warns when the signing key path does not exist" {
    _scaffold_repo
    git config --file "$GIT_GLOBAL" commit.gpgsign true
    git config --file "$GIT_GLOBAL" gpg.format ssh
    git config --file "$GIT_GLOBAL" user.signingkey "$BATS_TEST_TMPDIR/missing.pub"
    _run_doctor
    assert_success
    assert_output --partial "WARN commit signing"
}

# ── core.hooksPath verdict, per delivery mode ─────────────────────────────────
# Devcontainer mode wires it in setup-git-conf.sh; direnv mode wires it on
# dev-shell entry (githooksPathHook, #1112). Either way the wired state is the
# same value, so the PASS verdict must hold in both.

@test "consumer doctor reports PASS for core.hooksPath in devcontainer mode" {
    _scaffold_repo devcontainer
    git -C "$WS" config core.hooksPath .githooks
    _run_doctor
    assert_success
    assert_output --partial "PASS git hooks"
    refute_output --partial "WARN git hooks"
}

@test "consumer doctor reports PASS for core.hooksPath in direnv mode" {
    _scaffold_repo direnv
    git -C "$WS" config core.hooksPath .githooks
    _run_doctor
    assert_success
    assert_output --partial "PASS git hooks"
    refute_output --partial "WARN git hooks"
}

@test "consumer doctor warns and names the value when core.hooksPath points elsewhere" {
    _scaffold_repo direnv
    git -C "$WS" config core.hooksPath .git/hooks
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "core.hooksPath=.git/hooks"
    assert_output --partial "git config core.hooksPath .githooks"
}

# ── remediation hint: consumer entry points, never devkit's installer ─────────

@test "consumer doctor gives the plain git command in an ad-hoc checkout" {
    # No .vig-os at all: a clone outside both delivery modes. Nothing wires
    # core.hooksPath there, so the only honest fix is the direct command.
    git -c init.defaultBranch=main init -q "$WS"
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "core.hooksPath not set"
    assert_output --partial "run: git config core.hooksPath .githooks"
}

@test "consumer doctor names the devcontainer setup when hooks are inert in devcontainer mode" {
    _scaffold_repo devcontainer
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "run: git config core.hooksPath .githooks"
    assert_output --partial "devcontainer"
}

@test "consumer doctor names the dev shell when hooks are inert in direnv mode" {
    _scaffold_repo direnv
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "run: git config core.hooksPath .githooks"
    assert_output --partial "direnv allow"
}

@test "consumer doctor names both entry points in both mode" {
    _scaffold_repo both
    _run_doctor
    assert_success
    assert_output --partial "WARN git hooks"
    assert_output --partial "devcontainer"
    assert_output --partial "direnv allow"
}

@test "consumer doctor gives the plain git command in bare mode" {
    # `bare` ships standards only — no container, no flake — so nothing wires
    # core.hooksPath and no entry point can be named.
    _scaffold_repo bare
    _run_doctor
    assert_success
    assert_output --partial "run: git config core.hooksPath .githooks"
    refute_output --partial "direnv allow"
}

@test "consumer doctor never points at devkit's own scripts/init.sh" {
    # devkit's installer is not a consumer entry point; a consumer repo has no
    # scripts/init.sh at all.
    for mode in devcontainer direnv both bare; do
        rm -rf "$WS"
        mkdir -p "$WS"
        cp "$PROJECT_ROOT/assets/workspace/justfile" "$WS/justfile"
        _scaffold_repo "$mode"
        _run_doctor
        assert_success
        refute_output --partial "scripts/init.sh"
    done
}

# ── drift guard between the two doctor implementations ────────────────────────
# The consumer recipe is a deliberate second implementation (different
# remediation hints, different modes, no scripts/init.sh), so nothing but a
# test keeps the two from drifting apart on WHAT they check. Pin the shared
# expectation: identical check labels, identical PASS/WARN idiom, exit 0.

# Emit the sorted check labels of a doctor recipe: $1 justfile, $2 working dir.
_check_labels() {
    env -u SSH_AUTH_SOCK PATH="$STUBS:$PATH" \
        GIT_CONFIG_GLOBAL="$GIT_GLOBAL" GIT_CONFIG_SYSTEM=/dev/null \
        just --justfile "$1" --working-directory "$2" doctor |
        sed -n 's/^\(PASS\|WARN\) \([^:]*\):.*/\2/p' | sort
}

@test "consumer doctor checks exactly what devkit's doctor checks" {
    _scaffold_repo direnv
    local devkit_ws="$BATS_TEST_TMPDIR/devkit"
    mkdir -p "$devkit_ws"
    git -c init.defaultBranch=main init -q "$devkit_ws"

    local consumer devkit
    consumer="$(_check_labels "$WS/justfile" "$WS")"
    devkit="$(_check_labels "$PROJECT_ROOT/justfile" "$devkit_ws")"

    echo "consumer labels: $consumer"
    echo "devkit labels:   $devkit"
    [ -n "$consumer" ]
    [ "$consumer" = "$devkit" ]
}
