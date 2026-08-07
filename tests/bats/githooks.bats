#!/usr/bin/env bats
# BATS tests for workspace githook IN_CONTAINER guard
#
# Verifies that .githooks/{pre-commit,prepare-commit-msg,commit-msg} block
# commits when IN_CONTAINER is not "true" (i.e. outside the devcontainer).
# Refs: #238

bats_require_minimum_version 1.5.0

setup() {
    load test_helper
    HOOKS_DIR="$PROJECT_ROOT/assets/workspace/.githooks"
}

# ── pre-commit ────────────────────────────────────────────────────────────────

@test "pre-commit blocks when IN_CONTAINER is unset" {
    run env -u IN_CONTAINER -u IN_NIX_SHELL bash "$HOOKS_DIR/pre-commit"
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "pre-commit blocks when IN_CONTAINER is empty" {
    run env -u IN_NIX_SHELL IN_CONTAINER="" bash "$HOOKS_DIR/pre-commit"
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "pre-commit blocks when IN_CONTAINER is false" {
    run env -u IN_NIX_SHELL IN_CONTAINER="false" bash "$HOOKS_DIR/pre-commit"
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "pre-commit does not show guard message when IN_CONTAINER is true" {
    run -127 env PATH="/nonexistent" IN_CONTAINER="true" /bin/bash "$HOOKS_DIR/pre-commit"
    refute_output --partial "Please commit your changes within the dev container"
}

# ── prepare-commit-msg ────────────────────────────────────────────────────────

@test "prepare-commit-msg blocks when IN_CONTAINER is unset" {
    run env -u IN_CONTAINER -u IN_NIX_SHELL bash "$HOOKS_DIR/prepare-commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "prepare-commit-msg blocks when IN_CONTAINER is empty" {
    run env -u IN_NIX_SHELL IN_CONTAINER="" bash "$HOOKS_DIR/prepare-commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "prepare-commit-msg blocks when IN_CONTAINER is false" {
    run env -u IN_NIX_SHELL IN_CONTAINER="false" bash "$HOOKS_DIR/prepare-commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "prepare-commit-msg does not show guard message when IN_CONTAINER is true" {
    run -127 env PATH="/nonexistent" IN_CONTAINER="true" /bin/bash "$HOOKS_DIR/prepare-commit-msg" /dev/null
    refute_output --partial "Please commit your changes within the dev container"
}

# ── commit-msg ────────────────────────────────────────────────────────────────

@test "commit-msg blocks when IN_CONTAINER is unset" {
    run env -u IN_CONTAINER -u IN_NIX_SHELL bash "$HOOKS_DIR/commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "commit-msg blocks when IN_CONTAINER is empty" {
    run env -u IN_NIX_SHELL IN_CONTAINER="" bash "$HOOKS_DIR/commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "commit-msg blocks when IN_CONTAINER is false" {
    run env -u IN_NIX_SHELL IN_CONTAINER="false" bash "$HOOKS_DIR/commit-msg" /dev/null
    assert_failure
    assert_output --partial "Please commit your changes within the dev container"
}

@test "commit-msg does not show guard message when IN_CONTAINER is true" {
    run -127 env PATH="/nonexistent" IN_CONTAINER="true" /bin/bash "$HOOKS_DIR/commit-msg" /dev/null
    refute_output --partial "Please commit your changes within the dev container"
}
