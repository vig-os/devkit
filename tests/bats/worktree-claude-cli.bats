#!/usr/bin/env bats
# BATS tests for the claude-CLI migration of the worktree recipes (#627).
#
# Static recipe-grep checks only: assert that the worktree justfiles drive the
# `claude` CLI and that no `cursor-agent` invocation survives. The full
# functional rewrite of worktree.bats is tracked separately (#630).

setup() {
    load test_helper
    WT_MAIN="${PROJECT_ROOT}/justfile.worktree"
    WT_TEMPLATE="${PROJECT_ROOT}/assets/workspace/.devcontainer/justfile.worktree"
}

@test "justfile.worktree has no cursor-agent invocation" {
    run grep -nE 'cursor-agent|agent chat' "$WT_MAIN"
    assert_failure
}

@test "template justfile.worktree has no cursor-agent invocation" {
    run grep -nE 'cursor-agent|agent chat' "$WT_TEMPLATE"
    assert_failure
}

@test "justfile.worktree drives the claude CLI in tmux sessions" {
    run grep -nE 'claude --dangerously-skip-permissions' "$WT_MAIN"
    assert_success
}

@test "template justfile.worktree drives the claude CLI in tmux sessions" {
    run grep -nE 'claude --dangerously-skip-permissions' "$WT_TEMPLATE"
    assert_success
}

@test "justfile.worktree checks for the claude binary as a prerequisite" {
    run grep -nE 'command -v claude' "$WT_MAIN"
    assert_success
}
