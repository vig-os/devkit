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

# ── devc-upgrade removal (#1421) ──────────────────────────────────────────────
# The devkit-upgrade workflow's adoption PRs are the upgrade path; the local
# devc-upgrade recipe wrapped `install.sh --force` and steered users around the
# reviewed flow. Guard against reintroduction, and pin the notification's new
# contract: adoption-PR guidance when the workflow ships, one-liner fallback.

@test "devc-upgrade recipe is gone from the scaffold (#1421)" {
    run grep -F 'devc-upgrade' assets/workspace/.devcontainer/justfile.devc
    assert_failure
}

@test "version-check notification names the adoption-PR flow, not a removed recipe (#1421)" {
    local script=assets/workspace/.devcontainer/scripts/version-check.sh
    run grep -F 'devc-upgrade' "$script"
    assert_failure
    run bash -c "awk '/^notify_update\(\) \{/,/^\}/' '$script' | grep -F 'devkit-upgrade.yml'"
    assert_success
    run bash -c "awk '/^notify_update\(\) \{/,/^\}/' '$script' | grep -F 'adoption PR'"
    assert_success
    run bash -c "awk '/^notify_update\(\) \{/,/^\}/' '$script' | grep -F 'install.sh | bash -s -- --force'"
    assert_success
}


@test "release recipes dispatch their workflow from the expected ref" {
    # recipe:expected-REF table; prepare-release cuts from dev, the rest act on
    # the release branch.
    local table=(
        'prepare-release:REF="dev"'
        'finalize-release:REF="release/{{ version }}"'
        'promote-release:REF="release/{{ version }}"'
        'publish-candidate:REF="release/{{ version }}"'
        'abandon-release:REF="dev"'
    )
    for entry in "${table[@]}"; do
        recipe="${entry%%:*}"
        expected="${entry#*:}"
        echo "recipe: $recipe expects $expected"
        run bash -lc "awk '/^$recipe version ref=\"\" \\*flags:/{flag=1; next} /^\$/{if(flag){exit}} flag' justfile.gh | grep -Fq -- '$expected'"
        assert_success
    done
}

@test "abandon-release workflow refuses a published release and deletes as the Release App" {
    # #1504: the abandon path is safe only while the X.Y.Z Release is a draft —
    # a published release tombstones its tag name permanently (the 1.5.0 ghost).
    # The workflow must gate on isDraft, do the tag delete with the Release App
    # (tag-ruleset bypass, same machinery as the RC prune), keep the
    # release-attached-tag guard, close the release PR, and drop the branch.
    local wf=.github/workflows/abandon-release.yml
    run bash -lc "grep -Fq -- '.draft' $wf && grep -Fq -- 'RELEASE_APP_CLIENT_ID' $wf && grep -Fq -- 'git/refs/tags/' $wf && grep -Fq -- 'git/refs/heads/' $wf && grep -Fq -- 'gh pr close' $wf"
    assert_success
    # Published (non-draft) releases must be an explicit hard refusal.
    run bash -lc "grep -Eq -- 'published|tombstone' $wf"
    assert_success
}

@test "prepare-release workflow defines rollback job on failure or cancellation" {
    # #1059 moved the inline `if: failure()` rollback step into a dedicated
    # `rollback` job so it also covers the extension and open-pr jobs. Same
    # guard, new shape: the rollback exists and triggers on any phase failure.
    # #1078: a run cancelled after the freeze commit must roll back too, so
    # each phase's guard also matches `result == 'cancelled'`.
    run bash -lc "grep -Eq -- '^  rollback:' .github/workflows/prepare-release.yml && grep -Fq -- 'name: Roll back prepare-release side effects' .github/workflows/prepare-release.yml && grep -Fq -- \"needs.prepare.result == 'failure'\" .github/workflows/prepare-release.yml && grep -Fq -- \"needs.extension.result == 'failure'\" .github/workflows/prepare-release.yml && grep -Fq -- \"needs.open-pr.result == 'failure'\" .github/workflows/prepare-release.yml && grep -Fq -- \"needs.prepare.result == 'cancelled'\" .github/workflows/prepare-release.yml && grep -Fq -- \"needs.extension.result == 'cancelled'\" .github/workflows/prepare-release.yml && grep -Fq -- \"needs.open-pr.result == 'cancelled'\" .github/workflows/prepare-release.yml"
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
    # #1059: the PR-open step now lives in the `open-pr` job, so the region ends
    # at the following `rollback:` job instead of the old inline rollback step.
    run bash -lc "! awk '/^      - name: Create draft PR to main/{flag=1} /^  rollback:/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Testing Checklist' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^  rollback:/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### When Ready to Release' && ! awk '/^      - name: Create draft PR to main/{flag=1} /^  rollback:/{flag=0} flag {print}' .github/workflows/prepare-release.yml | grep -Fq -- '### Related'"
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

@test "smoke-test dispatch seeding awk is bounded and synthesizes ### Changed (#1403)" {
    # The seeding awk must clear its Unreleased state at the next release
    # heading (the old version leaked in_unreleased into released sections)
    # and must synthesize a ### Changed heading when Unreleased lacks one.
    run bash -lc 'grep -Fq -- "in_unreleased && !seeded && /^## \[/" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "print \"### Changed\"" assets/smoke-test/.github/workflows/repository-dispatch.yml'
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

@test "smoke-test dispatch gates the final release on human PR approval instead of self-approving" {
    run bash -lc "grep -Fq -- 'Gate final release on human approval of release PR' assets/smoke-test/.github/workflows/repository-dispatch.yml && ! grep -Fq -- 'gh pr review' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'reviewDecision' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch publishes installer deletions to the deploy branch (#1443)" {
    # commit-action builds its tree additively from working-tree contents, so
    # paths the installer deleted (retired scaffold paths, #1348) never reach
    # the deploy branch and the scaffold-drift gate rejects the PR. The deploy
    # job must publish those deletions explicitly (null-sha tree entries, the
    # same tree-API pattern as the scaffolded devkit-upgrade.yml).
    run bash -lc 'grep -Fq -- "Publish installer deletions via verified API commit" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "git ls-files --deleted" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "{path: \$p, mode: \"100644\", type: \"blob\", sha: null}" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch deploy branch name is dot-free (#1444)" {
    # The scaffolded CI branch-name gate (#1432) allows chore branches only as
    # ^chore/[a-z0-9]+(-[a-z0-9]+)*$ — dots rejected. The live listener was
    # hand-fixed (devkit-smoke-test#354) but the template SSoT must match, or
    # every deploy reverts the fix and the next train's deploy PR fails CI.
    run bash -lc 'grep -Fq -- "BRANCH_NAME=\"chore/deploy-\${TAG//./-}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml && ! grep -Fq -- "BRANCH_NAME=\"chore/deploy-\${TAG}\"" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch preflight validates required workflow contract" {
    run bash -lc "grep -Fq -- 'Preflight check required release workflows on dispatch ref' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'REQUIRED_WORKFLOWS=(prepare-release.yml release.yml promote-release.yml)' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'for workflow_file in \"\${REQUIRED_WORKFLOWS[@]}\"; do' assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- 'WORKFLOW_CHECK_OUTPUT=\"\$(gh workflow view \"\${workflow_file}\" --ref \"\${WORKFLOW_REF}\" --yaml 2>&1 >/dev/null)\"' assets/smoke-test/.github/workflows/repository-dispatch.yml"
    assert_success
}

@test "smoke-test dispatch wait logic binds to the dispatched prepare-release run (#1477)" {
    # The pre-#1477 guard was the id ordering alone, which matched a stale
    # completed run and let the wait pass without ever observing its own
    # dispatch. The baseline stays, but the wait must also bind on the dispatch
    # stamp; full shape + behaviour coverage lives in
    # tests/test_smoke_dispatch_wait.py.
    run bash -lc 'grep -Fq -- "Capture latest prepare-release run id" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh run list --workflow prepare-release.yml --branch \"\${WORKFLOW_REF}\" --event workflow_dispatch" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "BEFORE_RUN_ID: \${{ steps.capture_prepare_before.outputs.before_run_id }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "DISPATCH_TS: \${{ steps.trigger_prepare.outputs.dispatch_ts }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && ! grep -Fq -- "[ \"\${RUN_ID}\" -gt \"\${BEFORE_RUN_ID}\" ]" assets/smoke-test/.github/workflows/repository-dispatch.yml'
    assert_success
}

@test "smoke-test dispatch wait logic binds to the dispatched release run (#1477)" {
    run bash -lc 'grep -Fq -- "Capture latest release run id" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "gh run list --workflow release.yml --branch \"\${WORKFLOW_REF}\" --event workflow_dispatch" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "BEFORE_RUN_ID: \${{ steps.capture_release_before.outputs.before_run_id }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "DISPATCH_TS: \${{ steps.trigger_release.outputs.dispatch_ts }}" assets/smoke-test/.github/workflows/repository-dispatch.yml && grep -Fq -- "select(.createdAt >= \$ts and .databaseId > (\$before | tonumber))" assets/smoke-test/.github/workflows/repository-dispatch.yml'
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

@test "release caller and reusable workflows keep GITHUB_TOKEN read-only (writes ride App tokens) (#1136)" {
    run bash -lc "awk '/^  core:/{flag=1} /^  extension:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'actions: read' && awk '/^  core:/{flag=1} /^  extension:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'contents: read' && awk '/^  core:/{flag=1} /^  extension:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'pull-requests: read' && awk '/^  publish:/{flag=1} /^  rollback:/{flag=0} flag {print}' assets/workspace/.github/workflows/release.yml | grep -Fq -- 'contents: read' && awk '/^  validate:/{flag=1} /^  finalize:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'pull-requests: read' && awk '/^  finalize:/{flag=1} /^  test:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'actions: read' && awk '/^  finalize:/{flag=1} /^  test:/{flag=0} flag {print}' assets/workspace/.github/workflows/release-core.yml | grep -Fq -- 'contents: read'"
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
    # #1059 moved the workspace-mirror commit into prepare-release-extension.yml,
    # so the guard covers both files where FILE_PATHS values now live.
    run bash -lc "[ -r .github/workflows/prepare-release.yml ] && [ -r .github/workflows/prepare-release-extension.yml ] && ! grep -E 'FILE_PATHS:.*CHANGELOG\.md[[:space:]]+[^[:space:]]' .github/workflows/prepare-release.yml .github/workflows/prepare-release-extension.yml"
    assert_success
}

@test "release workflow joins finalization file paths with commas for commit-action" {
    run bash -lc "awk '/^      - name: Collect finalization files/{flag=1} /^      - name: Commit finalization changes via API/{flag=0} flag {print}' .github/workflows/release.yml | grep -Fq \"tr '\\n' ','\""
    assert_success
}

# ── uvx native-wheel libstdc++ helper (#1181) ─────────────────────────────────
# On a non-Python direnv-mode consumer the CI preamble keeps the Nix CPython on
# PATH, whose loader does not search /usr/lib, so a uvx tool's manylinux native
# wheel (e.g. otterdog's rjsonnet) fails to import with
# "libstdc++.so.6: cannot open shared object file" (org-config#40). The base
# `with-native-libs` recipe wraps ONE command with a command-scoped
# LD_LIBRARY_PATH sourced from $VIGOS_STDCPP_LIB (dev-shell export) or derived
# from the on-PATH `cc` wrapper, degrading to a no-op when neither is available.
# It lives in the root justfile (all delivery modes), not justfile.devc which is
# devcontainer-only — direnv-mode CI is exactly the case that needs it.

# Materialize the scaffolded root justfile plus two `cc` stubs in a temp dir:
# `found/cc` echoes an absolute path (gcc's behavior when it resolves the lib),
# `notfound/cc` echoes the bare name back (gcc's behavior when it cannot).
_with_native_libs_fixture() {
    NL_DIR="$BATS_TEST_TMPDIR/nl"
    mkdir -p "$NL_DIR/found" "$NL_DIR/notfound"
    cp "$PROJECT_ROOT/assets/workspace/justfile" "$NL_DIR/justfile"
    cat > "$NL_DIR/found/cc" <<'STUB'
#!/usr/bin/env bash
[ "$1" = "-print-file-name=libstdc++.so.6" ] && echo /opt/fake/lib/libstdc++.so.6
STUB
    cat > "$NL_DIR/notfound/cc" <<'STUB'
#!/usr/bin/env bash
[ "$1" = "-print-file-name=libstdc++.so.6" ] && echo libstdc++.so.6
STUB
    chmod +x "$NL_DIR/found/cc" "$NL_DIR/notfound/cc"
}

@test "root justfile ships the with-native-libs helper recipe (#1181)" {
    run grep -qE '^with-native-libs \+command:' assets/workspace/justfile
    assert_success
}

@test "with-native-libs derives LD_LIBRARY_PATH from the on-PATH cc wrapper (#1181)" {
    _with_native_libs_fixture
    run env -u LD_LIBRARY_PATH PATH="$NL_DIR/found:$PATH" \
        just -f "$NL_DIR/justfile" -d "$NL_DIR" with-native-libs env
    assert_success
    assert_line "LD_LIBRARY_PATH=/opt/fake/lib"
}

@test "with-native-libs prefers VIGOS_STDCPP_LIB over deriving from cc (#1181)" {
    _with_native_libs_fixture
    run env -u LD_LIBRARY_PATH VIGOS_STDCPP_LIB=/from/var PATH="$NL_DIR/found:$PATH" \
        just -f "$NL_DIR/justfile" -d "$NL_DIR" with-native-libs env
    assert_success
    assert_line "LD_LIBRARY_PATH=/from/var"
}

@test "with-native-libs no-ops cleanly when libstdc++ is not found (#1181)" {
    # A true no-op: LD_LIBRARY_PATH stays UNSET, not set-to-empty — an empty
    # value is itself one empty entry, which the dynamic loader treats as the
    # current working directory.
    _with_native_libs_fixture
    run env -u LD_LIBRARY_PATH PATH="$NL_DIR/notfound:$PATH" \
        just -f "$NL_DIR/justfile" -d "$NL_DIR" with-native-libs env
    assert_success
    refute_line --regexp '^LD_LIBRARY_PATH='
}

@test "with-native-libs prepends to an existing LD_LIBRARY_PATH (#1181)" {
    _with_native_libs_fixture
    run env LD_LIBRARY_PATH=/pre/existing PATH="$NL_DIR/found:$PATH" \
        just -f "$NL_DIR/justfile" -d "$NL_DIR" with-native-libs env
    assert_success
    assert_line "LD_LIBRARY_PATH=/opt/fake/lib:/pre/existing"
}

@test "with-native-libs leaves an existing LD_LIBRARY_PATH untouched when nothing resolves (#1181)" {
    # With an empty prefix a naive composition yields ":/pre/existing" — the
    # leading empty entry means "current working directory" to the dynamic
    # loader, silently adding cwd to the library search path (a planted
    # libstdc++.so.6 in an untrusted directory would be loaded). The caller's
    # value must pass through byte-identical, no leading colon.
    _with_native_libs_fixture
    run env LD_LIBRARY_PATH=/pre/existing PATH="$NL_DIR/notfound:$PATH" \
        just -f "$NL_DIR/justfile" -d "$NL_DIR" with-native-libs env
    assert_success
    assert_line "LD_LIBRARY_PATH=/pre/existing"
    refute_output --partial "LD_LIBRARY_PATH=:"
}

# ── recipe skip/exit-5 semantics (#1478) ──────────────────────────────────────
# The scaffolded recipes are guarded on `[ -f pyproject.toml ]`, so a repo whose
# Python project was deleted ran NOTHING and exited 0 — silently (#1466). Two
# mitigations: the guard now reports the skip instead of no-oping in silence,
# and pytest's exit 5 ("no tests collected") is swallowed ONLY while the repo has
# no `tests/` directory. Once a test directory exists, zero collected is a
# signal, not a no-op (#1281 narrowed, not reverted).

_recipe_fixture() {
    RC_DIR="$BATS_TEST_TMPDIR/recipes"
    mkdir -p "$RC_DIR/bin"
    cp "$PROJECT_ROOT/assets/workspace/justfile" "$RC_DIR/justfile"
    cp "$PROJECT_ROOT/assets/workspace/justfile.project" "$RC_DIR/justfile.project"
    # `just` substitutes {{SHORT_NAME}} at scaffold time; do the same here.
    sed -i 's/{{SHORT_NAME}}/testproj/' "$RC_DIR/justfile.project"
}

# A `uv` stub whose `run pytest` exits with $1 (5 = no tests collected).
_uv_stub() {
    cat > "$RC_DIR/bin/uv" <<STUB
#!/usr/bin/env bash
echo "uv \$*"
exit $1
STUB
    chmod +x "$RC_DIR/bin/uv"
}

@test "just test reports the skip when pyproject.toml is absent (#1478)" {
    _recipe_fixture
    run just -f "$RC_DIR/justfile" -d "$RC_DIR" test
    assert_success
    assert_output --partial "pyproject.toml"
    assert_output --partial "skipping"
}

@test "just lint/format/sync report the skip when pyproject.toml is absent (#1478)" {
    _recipe_fixture
    for recipe in lint format sync; do
        run just -f "$RC_DIR/justfile" -d "$RC_DIR" "$recipe"
        assert_success
        assert_output --partial "skipping"
    done
}

@test "just test swallows pytest exit 5 when there is no tests/ directory (#1281)" {
    _recipe_fixture
    _uv_stub 5
    touch "$RC_DIR/pyproject.toml"
    run env PATH="$RC_DIR/bin:$PATH" just -f "$RC_DIR/justfile" -d "$RC_DIR" test
    assert_success
}

@test "just test propagates pytest exit 5 once a tests/ directory exists (#1478)" {
    _recipe_fixture
    _uv_stub 5
    touch "$RC_DIR/pyproject.toml"
    mkdir -p "$RC_DIR/tests"
    run env PATH="$RC_DIR/bin:$PATH" just -f "$RC_DIR/justfile" -d "$RC_DIR" test
    assert_failure
}

@test "just test-cov propagates pytest exit 5 once a tests/ directory exists (#1478)" {
    _recipe_fixture
    _uv_stub 5
    touch "$RC_DIR/pyproject.toml"
    mkdir -p "$RC_DIR/tests"
    run env PATH="$RC_DIR/bin:$PATH" just -f "$RC_DIR/justfile" -d "$RC_DIR" test-cov
    assert_failure
}

@test "just test still propagates a real pytest failure (#1478)" {
    _recipe_fixture
    _uv_stub 1
    touch "$RC_DIR/pyproject.toml"
    run env PATH="$RC_DIR/bin:$PATH" just -f "$RC_DIR/justfile" -d "$RC_DIR" test
    assert_failure
}
