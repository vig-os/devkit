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

@test "smoke-test dispatch computes base version output from tag" {
    run bash -lc "grep -Fq -- 'base_version:' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- \"sed 's/-rc[0-9]*\\$//'\" assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch generates minimal changelog for prepare-release freeze" {
    run bash -lc 'grep -Fq -- "cat > \"CHANGELOG.md\" <<CHLOG" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "## Unreleased" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "- Deploy devcontainer \${TAG}" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch repairs ownership when installer leaves root-owned files" {
    run bash -lc 'grep -Fq -- "NEEDS_CHOWN=false" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "sudo chown -R" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "OWNER_UID_GID=\"\$(id -u):\$(id -g)\"" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch waits for deploy PR merge before release orchestration" {
    run bash -lc 'grep -Fq -- "wait-deploy-merge:" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh pr view \"\${PR_URL}\" --json state --jq" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch grants PR read permission for deploy-merge polling" {
    run bash -lc 'grep -Fq -- "wait-deploy-merge:" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "pull-requests: read" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch removes publish-release job" {
    run bash -lc "! grep -Fq -- 'publish-release:' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch triggers downstream prepare and release workflows" {
    run bash -lc "grep -Fq -- 'cleanup-release:' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'gh workflow run prepare-release.yml --ref \"\${WORKFLOW_REF}\"' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'gh workflow run release.yml \\' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- '--ref \"\${WORKFLOW_REF}\" \\' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch preflight validates required workflow contract" {
    run bash -lc "grep -Fq -- 'Preflight check required release workflows on dispatch ref' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'REQUIRED_WORKFLOWS=(prepare-release.yml release.yml)' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'for workflow_file in \"\${REQUIRED_WORKFLOWS[@]}\"; do' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'WORKFLOW_CHECK_OUTPUT=\"\$(gh workflow view \"\${workflow_file}\" --ref \"\${WORKFLOW_REF}\" 2>&1)\"' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch wait logic tracks prepare-release run after dispatch" {
    run bash -lc 'grep -Fq -- "Capture latest prepare-release run id" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh run list --workflow prepare-release.yml --branch \"\${WORKFLOW_REF}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "BEFORE_RUN_ID: \${{ steps.capture_prepare_before.outputs.before_run_id }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "[ \"\${RUN_ID}\" -gt \"\${BEFORE_RUN_ID}\" ]" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch wait logic tracks release run after dispatch" {
    run bash -lc 'grep -Fq -- "Capture latest release run id" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh run list --workflow release.yml --branch \"\${WORKFLOW_REF}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "BEFORE_RUN_ID: \${{ steps.capture_release_before.outputs.before_run_id }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "[ \"\${RUN_ID}\" -gt \"\${BEFORE_RUN_ID}\" ]" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch readies release PR and syncs upstream changelog" {
    run bash -lc "grep -Fq -- 'gh pr ready' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'gh pr review' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'raw.githubusercontent.com/vig-os/devcontainer' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'contents/CHANGELOG.md' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch tolerates transient auto-merge enable failures" {
    run bash -lc 'grep -Fq -- "could not enable auto-merge yet; will retry" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch notifies upstream on orchestration failure" {
    run bash -lc "grep -Fq -- 'notify-failure:' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'gh issue create \\' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- '--repo vig-os/devcontainer' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch summary includes release-orchestration job results" {
    run bash -lc "grep -Fq -- 'needs.wait-deploy-merge.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.cleanup-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.trigger-prepare-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.ready-release-pr.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.trigger-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}
