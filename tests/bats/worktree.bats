#!/usr/bin/env bats
# BATS tests for repo-level worktree integration.
#
# Encapsulated command behavior (resolve-branch/derive-branch-summary) lives in:
#   packages/vig-utils/tests/test_shell_entrypoints.py

setup() {
    load test_helper
    WT_MAIN="${PROJECT_ROOT}/justfile.worktree"
    WT_TEMPLATE="${PROJECT_ROOT}/assets/workspace/.devcontainer/justfile.worktree"
}

# ── worktree-attach restart logic (#132) ───────────────────────────────────────
# Tests that worktree-attach restarts a stopped tmux session when the worktree
# directory exists. Uses WORKTREE_ATTACH_RESTART_CMD to avoid agent dependency.

@test "worktree-attach restarts stopped session when worktree dir exists" {
    [ "${CI:-}" = "true" ] && skip "tmux integration tests require interactive TTY"
    command -v tmux >/dev/null 2>&1 || skip "tmux not installed"
    command -v just >/dev/null 2>&1 || skip "just not installed"

    ISSUE=999999
    REPO=$(basename "$(cd "$PROJECT_ROOT" && git rev-parse --show-toplevel)")
    WT_BASE="$(dirname "$PROJECT_ROOT")/${REPO}-worktrees"
    WT_DIR="${WT_BASE}/${ISSUE}"
    SESSION="wt-${ISSUE}"

    mkdir -p "$WT_DIR"
    tmux new-session -d -s "$SESSION" -c "$WT_DIR" "true"
    sleep 1
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        tmux kill-session -t "$SESSION" 2>/dev/null || true
        skip "tmux session did not exit after 'true' (timing)"
    fi

    env WORKTREE_ATTACH_RESTART_CMD="sleep 5" timeout 3 just worktree-attach "$ISSUE" 2>/dev/null &
    sleep 2
    run tmux has-session -t "$SESSION" 2>/dev/null
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    rm -rf "$WT_DIR"
    rmdir "$WT_BASE" 2>/dev/null || true

    assert_success
}

# ── claude CLI launches without a trust prompt (#630) ──────────────────────────
# The worktree recipes drive the `claude` CLI with
# `--dangerously-skip-permissions`, which bypasses every permission and MCP
# approval prompt — so there is no interactive trust prompt to send-keys to
# (this replaces the old cursor-agent "send 'a' to approve" flow). Validate that
# the autonomous invocation runs inside a tmux session without stalling on a
# prompt.

@test "claude CLI launches in tmux without an interactive trust prompt" {
    [ "${CI:-}" = "true" ] && skip "tmux integration tests require interactive TTY"
    command -v tmux >/dev/null 2>&1 || skip "tmux not installed"
    command -v claude >/dev/null 2>&1 || skip "claude CLI not installed"

    SESSION="wt-test-claude-$$"
    TESTDIR="/tmp/bats-claude-$$"
    mkdir -p "$TESTDIR"

    tmux new-session -d -s "$SESSION" -c "$TESTDIR"
    tmux set-option -t "$SESSION" remain-on-exit on
    # Launch claude the same way the recipes do, but with a non-interactive
    # subcommand: if a trust prompt were shown the pane would stall instead of
    # printing the version string.
    tmux send-keys -t "$SESSION" "claude --dangerously-skip-permissions --version" Enter
    sleep 5

    run tmux capture-pane -t "$SESSION" -p
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    rm -rf "$TESTDIR"

    assert_success
    refute_output --partial "trust"
}

# ── worktree-attach ───────────────────────────────────────────────────────────

@test "worktree-attach errors when neither worktree dir nor session exists" {
    [ "${CI:-}" = "true" ] && skip "tmux integration tests require interactive TTY"
    command -v tmux >/dev/null 2>&1 || skip "tmux not installed"
    command -v just >/dev/null 2>&1 || skip "just not installed"

    run just worktree-attach 999998 2>&1
    assert_failure
    assert_output --partial "[ERROR]"
    assert_output --partial "No tmux session"
}

# ── worktree-clean filter mode (#158) ────────────────────────────────────────
# Default (stopped-only): clean only worktrees with no running tmux session.
# Mode "all": clean all worktrees (current behavior).

@test "worktree-clean stopped-only skips worktrees with running tmux session" {
    [ "${CI:-}" = "true" ] && skip "tmux integration tests require interactive TTY"
    command -v tmux >/dev/null 2>&1 || skip "tmux not installed"
    command -v just >/dev/null 2>&1 || skip "just not installed"

    ISSUE_SKIP=999996
    ISSUE_CLEAN=999995
    REPO=$(basename "$(cd "$PROJECT_ROOT" && git rev-parse --show-toplevel)")
    WT_BASE="$(dirname "$PROJECT_ROOT")/${REPO}-worktrees"
    DIR_SKIP="${WT_BASE}/${ISSUE_SKIP}"
    DIR_CLEAN="${WT_BASE}/${ISSUE_CLEAN}"
    SESSION_SKIP="wt-${ISSUE_SKIP}"

    mkdir -p "$DIR_SKIP" "$DIR_CLEAN"
    tmux new-session -d -s "$SESSION_SKIP" -c "$DIR_SKIP" "sleep 60"
    sleep 1
    tmux has-session -t "$SESSION_SKIP" || skip "tmux session did not start"

    run just worktree-clean 2>&1

    assert_success
    assert_output --partial "[SKIP]"
    assert_output --partial "999996"
    assert_output --partial "999995"
    assert [ ! -d "$DIR_CLEAN" ]
    assert [ -d "$DIR_SKIP" ]

    tmux kill-session -t "$SESSION_SKIP" 2>/dev/null || true
    rm -rf "$DIR_SKIP" "$DIR_CLEAN"
    rmdir "$WT_BASE" 2>/dev/null || true
}

@test "worktree-clean all removes worktrees with running tmux sessions" {
    [ "${CI:-}" = "true" ] && skip "tmux integration tests require interactive TTY"
    command -v tmux >/dev/null 2>&1 || skip "tmux not installed"
    command -v just >/dev/null 2>&1 || skip "just not installed"

    ISSUE=999994
    REPO=$(basename "$(cd "$PROJECT_ROOT" && git rev-parse --show-toplevel)")
    WT_BASE="$(dirname "$PROJECT_ROOT")/${REPO}-worktrees"
    DIR="${WT_BASE}/${ISSUE}"
    SESSION="wt-${ISSUE}"

    mkdir -p "$DIR"
    tmux new-session -d -s "$SESSION" -c "$DIR" "sleep 60"
    sleep 1
    tmux has-session -t "$SESSION" || skip "tmux session did not start"

    run just worktree-clean all 2>&1

    assert_success
    assert_output --partial "[WARNING]"
    assert_output --partial "Removed worktree"
    assert [ ! -d "$DIR" ]

    tmux kill-session -t "$SESSION" 2>/dev/null || true
    rm -rf "$DIR"
    rmdir "$WT_BASE" 2>/dev/null || true
}

@test "wt-clean alias works for stopped-only and all" {
    command -v just >/dev/null 2>&1 || skip "just not installed"

    run just wt-clean 2>&1
    assert_success

    run just wt-clean all 2>&1
    assert_success
}

@test "worktree-clean rejects invalid mode" {
    command -v just >/dev/null 2>&1 || skip "just not installed"

    run just worktree-clean invalid 2>&1
    assert_failure
    assert_output --partial "[ERROR]"
    assert_output --partial "Invalid mode"
}

# ── _wt_repo backtick tolerates a foreign-git cwd (#1203) ───────────────────────
# `just` evaluates the top-level `_wt_repo` backtick eagerly on EVERY invocation,
# so its `git rev-parse --show-toplevel` runs even for unrelated recipes. In a
# git worktree whose `.git` file points at a gitdir outside a (bind-mounted) tree
# — the bare-podman scaffold context from #1197 — git can't resolve the repo and
# leaked `fatal: not a git repository: (null)` to stderr on every `just` call.
@test "just does not leak a git fatal in a foreign-git worktree cwd (#1203)" {
    command -v just >/dev/null 2>&1 || skip "just not installed"

    local broken
    broken="$(mktemp -d)"
    printf 'gitdir: /nonexistent/path/outside\n' > "$broken/.git"

    run just -d "$broken" -f "$PROJECT_ROOT/justfile.worktree" --evaluate _wt_repo
    rm -rf "$broken"

    assert_success
    refute_output --partial "not a git repository"
    refute_output --partial "fatal:"
}

# ── worktree-start leaves shared core.hooksPath alone (#1463) ─────────────────
# `core.hooksPath` is SHARED repo config, not per-worktree: unsetting it from
# inside the new linked worktree disarmed the MAIN checkout's tracked .githooks
# shims repo-wide. A relative hooksPath resolves against each worktree's root
# and .githooks is tracked (present in every worktree), so when it is set the
# tracked shims already cover every hook stage in the new worktree —
# worktree-start must leave the config untouched and skip the prek install.
# Only a repo with no hooksPath configured at all still gets prek's shims
# (they land in the shared .git/hooks, the active hooks dir in that state).
#
# Tests drive the REAL worktree-start recipe (both the root copy and the
# scaffolded template) in a sandbox repo — with a bare origin so `git fetch`
# succeeds — under stubbed tools (tmux/claude/gh/prek/uv and the helper CLIs)
# and pinned git config, the same harness idiom as consumer-doctor.bats.

WT_BRANCH="bugfix/4242-wt-hookspath"

# Write the tool stubs worktree-start shells out to. `uv run <tool>` delegates
# to the stubbed helper CLIs on PATH, so one stub set serves both the root copy
# (`uv run resolve-branch`) and the template copy (bare `resolve-branch`).
_wt_stubs() {
    STUBS="$BATS_TEST_TMPDIR/stubs"
    STUB_LOG="$BATS_TEST_TMPDIR/stub.log"
    mkdir -p "$STUBS"
    : >"$STUB_LOG"
    cat >"$STUBS/gh" <<STUB
#!/usr/bin/env bash
case "\${1:-} \${2:-}" in
    "repo set-default") echo "stub/default" ;;
    "api user")         echo "tester" ;;
    "issue develop")    printf '%s\thttps://example.invalid\n' "$WT_BRANCH" ;;
esac
exit 0
STUB
    cat >"$STUBS/claude" <<'STUB'
#!/usr/bin/env bash
echo "logged in"
exit 0
STUB
    cat >"$STUBS/tmux" <<'STUB'
#!/usr/bin/env bash
echo "tmux $*" >>"$STUB_LOG"
exit 0
STUB
    cat >"$STUBS/prek" <<'STUB'
#!/usr/bin/env bash
echo "prek $*" >>"$STUB_LOG"
exit 0
STUB
    cat >"$STUBS/uv" <<'STUB'
#!/usr/bin/env bash
cmd="${1:-}"
shift || true
case "$cmd" in
    run) exec "$@" ;;
esac
exit 0
STUB
    cat >"$STUBS/resolve-branch" <<'STUB'
#!/usr/bin/env bash
[ "${1:-}" = "--help" ] && exit 0
awk 'NR==1 { print $1 }'
STUB
    cat >"$STUBS/derive-branch-summary" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
    chmod +x "$STUBS"/*
}

# Pin git config sources so host global/system state never leaks into the
# sandbox (or the assertions).
_wt_git() {
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git "$@"
}

# Build a sandbox: main/ checkout with tracked .githooks shims covering all
# three stages, plus a bare origin.git carrying the issue branch so the
# recipe's `git fetch origin <branch>` succeeds.
_wt_sandbox() {
    local root="$1" main="$1/main" hook
    mkdir -p "$main/.githooks"
    _wt_git -c init.defaultBranch=main init -q "$main"
    for hook in pre-commit commit-msg prepare-commit-msg; do
        printf '#!/usr/bin/env bash\nexit 0\n' >"$main/.githooks/$hook"
        chmod +x "$main/.githooks/$hook"
    done
    : >"$main/.gitmessage"
    _wt_git -C "$main" add -A
    _wt_git -C "$main" -c user.name=t -c user.email=t@example.com \
        -c commit.gpgsign=false commit -qm init
    _wt_git -C "$main" branch "$WT_BRANCH"
    _wt_git init -q --bare "$root/origin.git"
    _wt_git -C "$main" remote add origin "$root/origin.git"
    _wt_git -C "$main" push -q origin main "$WT_BRANCH"
}

_run_wt_start() {
    local file="$1" main="$2"
    run env PATH="$STUBS:$PATH" STUB_LOG="$STUB_LOG" \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
        just --justfile "$file" --working-directory "$main" worktree-start 4242
}

@test "worktree-start keeps the main checkout's core.hooksPath and skips prek (#1463)" {
    command -v just >/dev/null 2>&1 || skip "just not installed"

    local i=0 f box hook
    for f in "$WT_MAIN" "$WT_TEMPLATE"; do
        echo "file: $f"
        i=$((i + 1))
        box="$BATS_TEST_TMPDIR/set$i"
        _wt_stubs
        _wt_sandbox "$box"
        _wt_git -C "$box/main" config core.hooksPath .githooks

        _run_wt_start "$f" "$box/main"
        assert_success

        # Shared config survives: the main checkout keeps its tracked shims.
        run _wt_git -C "$box/main" config core.hooksPath
        assert_success
        assert_output ".githooks"

        # The linked worktree runs the same tracked shims — the relative
        # hooksPath resolves against the worktree root, all three stages.
        for hook in pre-commit commit-msg prepare-commit-msg; do
            assert_file_executable "$box/main-worktrees/4242/.githooks/$hook"
        done

        # No prek install: the tracked shims already cover the worktree.
        run grep "prek install" "$STUB_LOG"
        assert_failure
    done
}

@test "worktree-start still installs prek shims when no core.hooksPath is set (#1463)" {
    command -v just >/dev/null 2>&1 || skip "just not installed"

    local i=0 f box
    for f in "$WT_MAIN" "$WT_TEMPLATE"; do
        echo "file: $f"
        i=$((i + 1))
        box="$BATS_TEST_TMPDIR/unset$i"
        _wt_stubs
        _wt_sandbox "$box"

        _run_wt_start "$f" "$box/main"
        assert_success

        # Fallback: no hooksPath configured, so prek wires every hook stage
        # the repo uses into the shared .git/hooks (#778).
        run grep -- "prek install -t pre-commit -t commit-msg -t prepare-commit-msg" "$STUB_LOG"
        assert_success
    done
}
