#!/usr/bin/env bats
# BATS tests for repo-level worktree integration.
#
# Encapsulated command behavior (resolve-branch/derive-branch-summary) lives in:
#   packages/vig-utils/tests/test_shell_entrypoints.py

setup() {
    load test_helper
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

@test "worktree-start detects branch already checked out via worktree list" {
    # Validates the detection pattern used in worktree-start's guard:
    # git worktree list --porcelain | grep "branch refs/heads/$BRANCH"
    TMPDIR_TEST="$(mktemp -d)"
    git init "$TMPDIR_TEST/repo" >/dev/null 2>&1
    git -C "$TMPDIR_TEST/repo" config user.email "test@test.local"
    git -C "$TMPDIR_TEST/repo" config user.name "Test"
    git -C "$TMPDIR_TEST/repo" commit --allow-empty -m "init" >/dev/null 2>&1
    git -C "$TMPDIR_TEST/repo" checkout -b "feature/999997-test-branch" >/dev/null 2>&1

    # The current checkout should appear in worktree list
    run bash -c "git -C '$TMPDIR_TEST/repo' worktree list --porcelain | grep 'branch refs/heads/feature/999997-test-branch'"
    assert_success

    # A non-existent branch should NOT appear
    run bash -c "git -C '$TMPDIR_TEST/repo' worktree list --porcelain | grep 'branch refs/heads/feature/000000-nonexistent'"
    assert_failure

    rm -rf "$TMPDIR_TEST"
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
