#!/usr/bin/env bats
# BATS tests for workspace githook IN_CONTAINER guard
#
# Verifies that .githooks/{pre-commit,prepare-commit-msg,commit-msg} block
# commits when IN_CONTAINER is not "true" (i.e. outside the devcontainer).
# One test per IN_CONTAINER state, looping over the three hooks (they share
# the guard); the echoed hook name attributes any failure.
# Refs: #238

bats_require_minimum_version 1.5.0

HOOKS=(pre-commit prepare-commit-msg commit-msg)

setup() {
    load test_helper
    HOOKS_DIR="$PROJECT_ROOT/assets/workspace/.githooks"
}

# prepare-commit-msg and commit-msg expect a message-file argument.
_hook_args() {
    # commit-msg / prepare-commit-msg take a message-file argument; pre-commit
    # takes none. Populates the caller's `args` array.
    args=()
    [ "$1" = "pre-commit" ] || args=(/dev/null)
}

@test "githooks block when IN_CONTAINER is unset" {
    for hook in "${HOOKS[@]}"; do
        echo "hook: $hook"
        _hook_args "$hook"
        run env -u IN_CONTAINER -u IN_NIX_SHELL bash "$HOOKS_DIR/$hook" "${args[@]}"
        assert_failure
        assert_output --partial "Please commit your changes within the dev container"
    done
}

@test "githooks block when IN_CONTAINER is empty" {
    for hook in "${HOOKS[@]}"; do
        echo "hook: $hook"
        _hook_args "$hook"
        run env -u IN_NIX_SHELL IN_CONTAINER="" bash "$HOOKS_DIR/$hook" "${args[@]}"
        assert_failure
        assert_output --partial "Please commit your changes within the dev container"
    done
}

@test "githooks block when IN_CONTAINER is false" {
    for hook in "${HOOKS[@]}"; do
        echo "hook: $hook"
        _hook_args "$hook"
        run env -u IN_NIX_SHELL IN_CONTAINER="false" bash "$HOOKS_DIR/$hook" "${args[@]}"
        assert_failure
        assert_output --partial "Please commit your changes within the dev container"
    done
}

@test "githooks do not show the guard message when IN_CONTAINER is true" {
    for hook in "${HOOKS[@]}"; do
        echo "hook: $hook"
        _hook_args "$hook"
        run -127 env PATH="/nonexistent" IN_CONTAINER="true" /bin/bash "$HOOKS_DIR/$hook" "${args[@]}"
        refute_output --partial "Please commit your changes within the dev container"
    done
}
