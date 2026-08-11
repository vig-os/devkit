#!/usr/bin/env bats
# BATS tests for setup-gh-repo.sh

setup() {
    load test_helper
    SETUP_GH_REPO_SH="$PROJECT_ROOT/assets/workspace/.devcontainer/scripts/setup-gh-repo.sh"
    POST_CREATE_SH="$PROJECT_ROOT/assets/workspace/.devcontainer/scripts/post-create.sh"
}

@test "setup-gh-repo.sh is an executable bash script" {
    run test -x "$SETUP_GH_REPO_SH"
    assert_success
    run head -1 "$SETUP_GH_REPO_SH"
    assert_output "#!/bin/bash"
}

@test "setup-gh-repo.sh checks repo code-security-configuration status" {
    run grep 'code-security-configuration' "$SETUP_GH_REPO_SH"
    assert_success
}

@test "setup-gh-repo.sh detaches via code-security/configurations/detach endpoint" {
    run grep 'code-security/configurations/detach' "$SETUP_GH_REPO_SH"
    assert_success
}

@test "post-create.sh invokes setup-gh-repo.sh" {
    run grep 'setup-gh-repo.sh' "$POST_CREATE_SH"
    assert_success
}
