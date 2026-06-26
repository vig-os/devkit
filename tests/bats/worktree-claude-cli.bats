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
    DBS="${PROJECT_ROOT}/packages/vig-utils/src/vig_utils/shell/derive-branch-summary.sh"
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

# The launch command was migrated, but the worktree recipes also *read* agent
# config (model tiers, branch-naming rule). Those reads must point at the
# .claude/ SSoT, not the removed .cursor/ tree (#627).
@test "justfile.worktree reads agent config from .claude, not .cursor" {
    run grep -nE '\.cursor/(agent-models|rules)' "$WT_MAIN"
    assert_failure
}

@test "template justfile.worktree reads agent config from .claude, not .cursor" {
    run grep -nE '\.cursor/(agent-models|rules)' "$WT_TEMPLATE"
    assert_failure
}

# derive-branch-summary is invoked by worktree-start; it must drive the claude
# CLI, not the removed cursor-agent binary (#627).
@test "derive-branch-summary drives the claude CLI, not cursor-agent" {
    run grep -nE 'cursor-agent|agent --print|agent chat' "$DBS"
    assert_failure
}

@test "derive-branch-summary invokes the claude binary in print mode" {
    run grep -nE 'claude (--print|-p)' "$DBS"
    assert_success
}
