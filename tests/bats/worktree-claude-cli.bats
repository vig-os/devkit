#!/usr/bin/env bats
# BATS tests for the claude-CLI migration of the worktree recipes (#627).
#
# Static recipe-grep checks only: assert that the worktree justfiles drive the
# `claude` CLI and that no `cursor-agent` invocation survives. The main and
# template copies carry the same recipes, so each check loops over both files
# (the echoed path attributes any failure). The full functional rewrite of
# worktree.bats is tracked separately (#630).

setup() {
    load test_helper
    WT_MAIN="${PROJECT_ROOT}/justfile.worktree"
    WT_TEMPLATE="${PROJECT_ROOT}/assets/workspace/.devcontainer/justfile.worktree"
    WT_FILES=("$WT_MAIN" "$WT_TEMPLATE")
    DBS="${PROJECT_ROOT}/packages/vig-utils/src/vig_utils/shell/derive-branch-summary.sh"
}

@test "justfile.worktree copies have no cursor-agent invocation" {
    for f in "${WT_FILES[@]}"; do
        echo "file: $f"
        run grep -nE 'cursor-agent|agent chat' "$f"
        assert_failure
    done
}

@test "justfile.worktree copies drive the claude CLI in tmux sessions" {
    for f in "${WT_FILES[@]}"; do
        echo "file: $f"
        run grep -nE 'claude --dangerously-skip-permissions' "$f"
        assert_success
    done
}

@test "justfile.worktree checks for the claude binary as a prerequisite" {
    run grep -nE 'command -v claude' "$WT_MAIN"
    assert_success
}

# The launch command was migrated, but the worktree recipes also *read* agent
# config (model tiers, branch-naming rule). Those reads must point at the
# .claude/ SSoT, not the removed .cursor/ tree (#627).
@test "justfile.worktree copies read agent config from .claude, not .cursor" {
    for f in "${WT_FILES[@]}"; do
        echo "file: $f"
        run grep -nE '\.cursor/(agent-models|rules)' "$f"
        assert_failure
    done
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
