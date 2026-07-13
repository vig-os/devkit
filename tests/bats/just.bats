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

@test "justfile.gh namespaces git helpers to avoid consumer recipe collisions" {
    # The scaffold justfile.gh must not define bare `log`/`branch` recipes:
    # a consumer justfile.project defining its own `log`/`branch` would then
    # collide on import and break `just` entirely. Only gh-namespaced names.
    run bash -lc "! grep -qE '^(log|branch):' justfile.gh"
    assert_success
    run bash -lc "grep -qE '^gh-log:' justfile.gh && grep -qE '^gh-branch:' justfile.gh"
    assert_success
}

@test "justfile.gh imports alongside a consumer log/branch justfile without redefinition errors" {
    collision_dir="$BATS_TEST_TMPDIR/collision"
    mkdir -p "$collision_dir"
    cp "$PROJECT_ROOT/justfile.gh" "$collision_dir/justfile.gh"
    cat > "$collision_dir/justfile.project" <<'EOF'
log:
    @echo consumer-log

branch:
    @echo consumer-branch
EOF
    cat > "$collision_dir/justfile" <<'EOF'
import 'justfile.gh'
import 'justfile.project'
EOF
    run just -f "$collision_dir/justfile" -d "$collision_dir" --list
    assert_success
    assert_output --partial "gh-log"
    assert_output --partial "gh-branch"
}

# ── pipefail shell in the root justfile (#854) ────────────────────────────────
# `set shell := ["bash","-euo","pipefail","-c"]` used to live only in the
# devc-managed justfile.devc, so in direnv/bare mode (no .devcontainer/) the
# identical justfile.project recipes ran under just's default `sh -cu` without
# pipefail. The setting belongs in the root justfile, which ships in every mode.

@test "root justfile template sets the pipefail shell (#854)" {
    run grep -qF 'set shell := ["bash", "-euo", "pipefail", "-c"]' \
        assets/workspace/justfile
    assert_success
}

@test "justfile.devc no longer duplicates the shell setting (SSoT, #854)" {
    run grep -qE '^[[:space:]]*set shell' assets/workspace/.devcontainer/justfile.devc
    assert_failure
}

@test "scaffolded root justfile loads with the pipefail shell set (#854)" {
    run bash -c "cd assets/workspace && just --summary >/dev/null"
    assert_success
}

# ── devc-upgrade honors the .vig-os pin (#854) ────────────────────────────────
# The scaffolded devc-upgrade recipe used to always curl install.sh from `main`,
# silently moving a pinned consumer to HEAD. It must read the pin (DEVKIT_VERSION,
# or legacy DEVCONTAINER_VERSION, #781) from .vig-os and upgrade to THAT
# generation instead.

@test "devc-upgrade reads DEVKIT_VERSION from .vig-os (#854, #781)" {
    run grep -q 'DEVKIT_VERSION' \
        assets/workspace/.devcontainer/justfile.devc
    assert_success
}

@test "devc-upgrade still honors a legacy DEVCONTAINER_VERSION pin (#781)" {
    run grep -q 'DEVCONTAINER_VERSION' \
        assets/workspace/.devcontainer/justfile.devc
    assert_success
}

@test "devc-upgrade curls install.sh from the pinned ref, not hard-wired main (#854)" {
    # The functional upgrade curl must interpolate the resolved ref (${REF}),
    # and no install.sh curl in the recipe may be pinned literally to /main/.
    # shellcheck disable=SC2016  # grepping for the LITERAL '${REF}' in the recipe
    run grep -q 'githubusercontent.com/vig-os/devkit/${REF}/install.sh' \
        assets/workspace/.devcontainer/justfile.devc
    assert_success
    run grep -F 'vig-os/devcontainer/main/install.sh' \
        assets/workspace/.devcontainer/justfile.devc
    assert_failure
}

@test "devc-upgrade forwards --version for a pinned consumer (#854)" {
    run grep -q -- '--version' assets/workspace/.devcontainer/justfile.devc
    assert_success
}

@test "prepare-release dispatches workflow from dev ref" {
    run bash -lc "awk '/^prepare-release version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile.gh | grep -Fq -- 'REF=\"dev\"'"
    assert_success
}

@test "finalize-release dispatches workflow from release branch ref" {
    run bash -lc "awk '/^finalize-release version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile.gh | grep -Fq -- 'REF=\"release/{{ version }}\"'"
    assert_success
}

@test "promote-release dispatches workflow from release branch ref" {
    run bash -lc "awk '/^promote-release version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile.gh | grep -Fq -- 'REF=\"release/{{ version }}\"'"
    assert_success
}

@test "publish-candidate dispatches workflow from release branch ref" {
    run bash -lc "awk '/^publish-candidate version ref=\"\" \\*flags:/{flag=1; next} /^$/{if(flag){exit}} flag' justfile.gh | grep -Fq -- 'REF=\"release/{{ version }}\"'"
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

@test "release workflow finalize job does not disable just install" {
    run bash -lc "awk '/^  finalize:/{flag=1} /^  build-and-test:/{flag=0} flag {print}' .github/workflows/release.yml | grep -Fq -- \"install-just: 'false'\""
    assert_failure
}

@test "prepare-release PR body omits persistent checklist and related sections" {
    run bash -lc "! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Testing Checklist' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### When Ready to Release' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^      - name: Roll back prepare-release side effects on failure/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Related'"
    assert_success
}

@test "release workflow refreshes release PR body from changelog" {
    run bash -lc 'grep -Fq -- "name: Refresh release PR body from finalized changelog" .github/workflows/release.yml && grep -Fq -- "CHANGELOG_CONTENT=\$(awk" .github/workflows/release.yml && grep -Fq -- "gh pr edit \"\$PR_NUMBER\" --body-file /tmp/release-pr-body.md" .github/workflows/release.yml'
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

@test "smoke-test dispatch validates workspace changelog exists after install" {
    run bash -lc 'grep -Fq -- "expected CHANGELOG.md after install (workspace scaffold)" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "CHANGELOG.md is not readable after ownership repair" assets/smoke-test/.github/workflows/repository-dispatch.yml'
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

@test "smoke-test dispatch triggers downstream prepare-release workflow" {
    run bash -lc 'grep -Fq -- "cleanup-release:" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh workflow run prepare-release.yml" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch preflight validates required workflow contract" {
    run bash -lc "grep -Fq -- 'Preflight check required release workflows on dispatch ref' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'REQUIRED_WORKFLOWS=(prepare-release.yml release.yml promote-release.yml)' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'for workflow_file in \"\${REQUIRED_WORKFLOWS[@]}\"; do' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'WORKFLOW_CHECK_OUTPUT=\"\$(gh workflow view \"\${workflow_file}\" --ref \"\${WORKFLOW_REF}\" --yaml 2>&1 >/dev/null)\"' assets/smoke-test/.github/workflows/repository-dispatch.yml"
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

@test "smoke-test dispatch triggers release workflow with base version and release kind" {
    run bash -lc 'grep -Fq -- "gh workflow run release.yml \\" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "-f version=\"\${BASE_VERSION}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "-f release-kind=\"\${RELEASE_KIND}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "needs: [validate, ready-release-pr]" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch waits for release PR required checks after release workflow" {
    run bash -lc 'grep -Fq -- "wait-release-pr-ci:" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "Poll release PR required checks until green" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "Waiting for release PR required checks" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "needs: [ready-release-pr, trigger-release]" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch readies release PR with release kind label" {
    run bash -lc 'grep -Fq -- "gh pr ready" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "release-kind:candidate" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "Label release PR with release kind" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch notifies upstream on orchestration failure" {
    run bash -lc "grep -Fq -- 'notify-failure:' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'gh issue create \\' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- '--repo vig-os/devkit' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch summary includes release-orchestration job results" {
    run bash -lc "grep -Fq -- 'needs.wait-deploy-merge.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.cleanup-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.trigger-prepare-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.ready-release-pr.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.trigger-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.wait-release-pr-ci.result' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'needs.trigger-promote-release.result' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "release workflow rollback resolves the toolchain independently of core outputs (#991)" {
    run bash -lc "grep -Fq -- 'resolve-toolchain:' assets/workspace/.github/workflows/release.yml && grep -Fq -- 'needs: [resolve-toolchain, core, extension, publish]' assets/workspace/.github/workflows/release.yml && grep -Fq -- 'image: \${{ needs.resolve-toolchain.outputs.image }}' assets/workspace/.github/workflows/release.yml"
    assert_success
}

@test "workspace promote-release resolves the toolchain and gates on draft release (#991)" {
    run bash -lc "grep -Fq -- 'resolve-toolchain:' assets/workspace/.github/workflows/promote-release.yml && grep -Fq -- 'group: publish-release' assets/workspace/.github/workflows/promote-release.yml && grep -Fq -- 'workflow_dispatch:' assets/workspace/.github/workflows/promote-release.yml && grep -Fq -- 'Verify draft GitHub Release exists' assets/workspace/.github/workflows/promote-release.yml && grep -Fq -- 'gh release edit' assets/workspace/.github/workflows/promote-release.yml"
    assert_success
}

@test "release workflows provision the toolchain in container jobs that run git (#991)" {
    # safe.directory (container mode) is now owned by the setup-devkit-toolchain
    # composite, run as the first step after checkout in every job.
    run bash -lc "awk '/^  validate:/{flag=1} /^  finalize:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'uses: ./.github/actions/setup-devkit-toolchain' && grep -Fq -- 'uses: ./.github/actions/setup-devkit-toolchain' assets/workspace/.github/workflows/release-publish.yml && [ \"$(grep -Fc -- 'uses: ./.github/actions/setup-devkit-toolchain' assets/workspace/.github/workflows/sync-main-to-dev.yml)\" -ge 2 ] && grep -Fq -- 'uses: ./.github/actions/setup-devkit-toolchain' assets/workspace/.github/workflows/release.yml"
    assert_success
}

@test "release caller and reusable workflows define explicit minimal permissions for gh operations" {
    run bash -lc "awk '/^  core:/{flag=1} /^  extension:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'actions: write' && awk '/^  core:/{flag=1} /^  extension:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'pull-requests: read' && awk '/^  publish:/{flag=1} /^  rollback:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'contents: write' && awk '/^  validate:/{flag=1} /^  finalize:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'pull-requests: read' && awk '/^  finalize:/{flag=1} /^  test:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'actions: write'"
    assert_success
}

@test "smoke-test dispatch exposes base_version and rc_number for cross-repo RC alignment" {
    run bash -lc "grep -Fq -- 'base_version=' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'rc_number=' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'steps.extract.outputs.base_version' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'steps.extract.outputs.rc_number' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "workspace release workflows accept rc-number for pinned candidate RC" {
    run bash -lc "grep -Fq -- 'rc-number:' assets/workspace/.github/workflows/release.yml && grep -Fq -- 'rc_number:' assets/workspace/.github/workflows/release.yml && grep -Fq -- 'rc_number:' assets/workspace/.github/workflows/release-core.yml"
    assert_success
}

@test "prepare-release workflow FILE_PATHS uses comma delimiter for multi-file values" {
    run bash -lc "[ -r .github/workflows/prepare-release.yml ] && ! grep -E 'FILE_PATHS:.*CHANGELOG\.md[[:space:]]+[^[:space:]]' .github/workflows/prepare-release.yml"
    assert_success
}

@test "release workflow joins finalization file paths with commas for commit-action" {
    run bash -lc "awk '/^      - name: Collect finalization files/{flag=1} /^      - name: Commit finalization changes via API/{flag=0} flag {print}' .github/workflows/release.yml | grep -Fq \"tr '\\n' ','\""
    assert_success
}
