#!/usr/bin/env bats
# BATS tests for justfile
#
# Tests the justfile recipes and configuration.
# These tests verify:
# - Default recipe lists available commands

setup() {
    load test_helper
}

@test "just without arguments lists available recipes" {
    run just
    assert_success
    assert_output --partial "Available recipes"
}

@test "prepare-release dispatches workflow from dev ref" {
    run bash -lc "awk '/^prepare-release version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile | grep -Fq -- 'REF=\"dev\"'"
    assert_success
}

@test "finalize-release dispatches workflow from release branch ref" {
    run bash -lc "awk '/^finalize-release version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile | grep -Fq -- 'REF=\"release/{{ version }}\"'"
    assert_success
}

@test "publish-candidate dispatches workflow from release branch ref" {
    run bash -lc "awk '/^publish-candidate version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile | grep -Fq -- 'REF=\"release/{{ version }}\"'"
    assert_success
}

@test "prepare-release workflow defines rollback step on failure" {
    run bash -lc "grep -Fq -- 'name: Roll back prepare-release side effects on failure' .github/workflows/prepare-release.yml"
    assert_success
}

@test "prepare-release workflow rollback deletes release branch ref" {
    run bash -lc "grep -Fq -- 'git/refs/heads/$RELEASE_BRANCH' .github/workflows/prepare-release.yml"
    assert_success
}

@test "release workflow regenerates docs during finalization" {
    run bash -lc "grep -Fq -- 'name: Regenerate docs for finalized release' .github/workflows/release.yml"
    assert_success
}

@test "release workflow commits dynamic finalization file paths" {
    run bash -lc "grep -Fq -- 'id: finalize-files' .github/workflows/release.yml && grep -Fq -- 'steps.finalize-files.outputs.file_paths' .github/workflows/release.yml"
    assert_success
}

@test "prepare-release PR body omits persistent checklist and related sections" {
    run bash -lc "! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Testing Checklist' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### When Ready to Release' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Related'"
    assert_success
}

@test "release workflow refreshes release PR body from changelog" {
    run bash -lc 'grep -Fq -- "name: Refresh release PR body from finalized changelog" .github/workflows/release.yml && grep -Fq -- "CHANGELOG_CONTENT=\$(sed -n" .github/workflows/release.yml && grep -Fq -- "gh pr edit \"\$PR_NUMBER\" --body-file /tmp/release-pr-body.md" .github/workflows/release.yml'
    assert_success
}

@test "candidate dispatch includes smoke-test source metadata payload fields" {
    run bash -lc "grep -Fq -- 'event_type=smoke-test-trigger' .github/workflows/release.yml && grep -Fq -- 'client_payload[source_repo]' .github/workflows/release.yml && grep -Fq -- 'client_payload[source_workflow]' .github/workflows/release.yml && grep -Fq -- 'client_payload[source_run_id]' .github/workflows/release.yml && grep -Fq -- 'client_payload[source_run_url]' .github/workflows/release.yml && grep -Fq -- 'client_payload[source_sha]' .github/workflows/release.yml && grep -Fq -- 'client_payload[correlation_id]' .github/workflows/release.yml"
    assert_success
}

@test "smoke-test dispatch template logs source metadata and writes summary" {
    run bash -lc "grep -Fq -- 'EFFECTIVE_SOURCE_RUN_URL=' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'source_run_url=' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'correlation_id=' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'GITHUB_STEP_SUMMARY' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}
