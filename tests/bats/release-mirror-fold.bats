#!/usr/bin/env bats
# BATS tests for the mirror-mode release fold and promote reset (#1424).
#
# The sibling render pins in init-workspace.bats assert that the steps are
# RENDERED. They cannot assert that the steps WORK — which is exactly how #1502
# (a newline-joined FILE_PATHS that commit-action parses as one comma-separated
# path, folding nothing while reporting success) and #1503 (a force-push that
# authenticates as the wrong identity) survived review and CI.
#
# So these tests EXECUTE the rendered `run:` blocks. Each block is extracted
# from the scaffolded YAML and run against a throwaway git fixture whose
# `origin` is a local bare repo: real `git fetch`/`checkout`/`diff`, real
# $GITHUB_OUTPUT, no network and no GitHub. The only things not covered are the
# two steps that genuinely need GitHub — commit-action itself and the
# force-push — which is why both are now gated on a locally verifiable
# precondition rather than trusted.

setup() {
    load test_helper
    MIRROR_WS="$BATS_FILE_TMPDIR/mirror-ws"
    RELEASE_CORE="$MIRROR_WS/.github/workflows/release-core.yml"
    PROMOTE="$MIRROR_WS/.github/workflows/promote-release.yml"
    # Exported here, not inside _run_block: `run` executes its command in a
    # subshell, so an export there would never reach the assertions.
    GITHUB_OUTPUT="$BATS_TEST_TMPDIR/github-output"
    export GITHUB_OUTPUT
    : >"$GITHUB_OUTPUT"
}

# Render the mirror-mode workspace ONCE for the whole file: every test here
# only reads the rendered YAML, and scaffold+upgrade is the slow part.
setup_file() {
    local root ws stub
    root="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    ws="$BATS_FILE_TMPDIR/mirror-ws"
    stub="$BATS_FILE_TMPDIR/stub-bin"
    mkdir -p "$ws" "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$root/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$root/assets/init-workspace.sh" --force --no-prompts --mode both \
        >"$ws.log" 2>&1 || { cat "$ws.log" >&2; return 1; }
    sed -i 's#^DEVKIT_SYNC_TARGET=.*#DEVKIT_SYNC_TARGET=sync/issue-mirror#' "$ws/.vig-os"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$root/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        bash "$root/assets/init-workspace.sh" --force --no-prompts \
        >>"$ws.log" 2>&1 || { cat "$ws.log" >&2; return 1; }
}

# Print the dedented body of the `run: |` block of step "$2" in workflow "$1".
# Steps sit at 6 spaces, their keys at 8, the run body at 10.
_extract_run() {
    awk -v step="$2" '
        index($0, "- name: " step) { found = 1; next }
        found && /^[[:space:]]*run: \|[[:space:]]*$/ { inrun = 1; next }
        inrun {
            if ($0 ~ /^[[:space:]]*$/) { print ""; next }
            if ($0 !~ /^          /) { exit }
            sub(/^          /, "")
            print
        }
    ' "$1"
}

# Run an extracted block in $PWD. Extra args are `NAME=value` step env vars.
# The outputs file is truncated per call so a test that runs two steps asserts
# on the second one's outputs only (truncating the FILE works from `run`'s
# subshell — only the exported variable would not).
_run_block() {
    local block="$1"
    shift
    : >"$GITHUB_OUTPUT"
    env "$@" bash "$block"
}

_out() { cat "$GITHUB_OUTPUT"; }

# A throwaway remote whose branches mimic a mirror-mode consumer mid-release:
#
#   main / release/1.2.3   docs/issues/issue-1.md          (last release's archive)
#   sync/issue-mirror      docs/issues/issue-2.md          (issue-1 RENAMED)
#                          docs/pull-requests/pr 9.md      (a path with spaces)
#
# The spaced path is the shape `git status --porcelain | awk '{print $2}'` gets
# wrong (#1502): porcelain C-quotes it, so awk yields `"docs/pull-requests/pr`.
# The rename pins the other half of the contract — the mirror dropping a path
# neither folds nor deletes it, because the archive only grows.
_mk_fixture() {
    local root="$1"
    mkdir -p "$root"
    git init -q -b main --bare "$root/origin.git"
    git clone -q "$root/origin.git" "$root/work"
    cd "$root/work" || return 1
    git config user.email test@example.com
    git config user.name "Test User"
    git config commit.gpgsign false

    mkdir -p docs/issues docs/pull-requests
    printf 'issue one\n' >docs/issues/issue-1.md
    git add -A
    git commit -qm "chore: seed archive"
    git push -q origin HEAD:refs/heads/main
    git push -q origin HEAD:refs/heads/release/1.2.3

    git checkout -q -b sync/issue-mirror
    git mv docs/issues/issue-1.md docs/issues/issue-2.md
    printf 'pr nine\n' >"docs/pull-requests/pr 9.md"
    git add -A
    git commit -qm "chore: sync issues and PRs"
    git push -q origin HEAD:refs/heads/sync/issue-mirror

    git checkout -q -B release/1.2.3 main
    git branch -q -D sync/issue-mirror
    git fetch -q origin
}

# Land the staged fold as a real commit on the remote release branch — what
# commit-action does in the job, minus GitHub.
_commit_fold() {
    git commit -qm "chore: fold sync mirror archive into release 1.2.3"
    git push -q origin HEAD:refs/heads/release/1.2.3
}

# ── the fold path list (#1502) ────────────────────────────────────────────────

@test "fold staging emits a single-line comma-joined path list (#1502)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"

    run _run_block "$block"
    assert_success

    # commit-action splits FILE_PATHS on commas, so the list must be ONE line
    # of comma-separated paths. A heredoc/newline-joined value is a single
    # unparsable path and folds nothing, silently (#1502).
    run _out
    assert_success
    assert_line 'eligible=true'
    assert_line 'file_paths=docs/issues/issue-2.md,docs/pull-requests/pr 9.md'
    refute_line --partial 'PATHS_EOF'
}

@test "fold staging leaves a mirror-side deletion out of the list (#1424)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"

    run _run_block "$block"
    assert_success
    # The mirror renamed issue-1.md away, but a pathspec checkout only writes
    # what the mirror HAS — and commit-action only adds and updates. So the
    # old path is neither folded nor removed: archives only grow.
    run _out
    refute_line --partial 'issue-1.md'
    assert [ -f docs/issues/issue-1.md ]
}

@test "fold staging reports the true path count (#1502)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"

    run _run_block "$block"
    assert_success
    assert_output --partial 'Folding 2 mirror archive path(s)'
}

@test "fold staging is a clean no-op when the release branch already matches (#1424)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    # Fold once and land it, so the second staging finds nothing to do.
    _run_block "$block" >/dev/null
    _commit_fold

    run _run_block "$block"
    assert_success
    run _out
    assert_line 'eligible=false'
    refute_line --partial 'file_paths='
}

@test "fold staging skips cleanly when the mirror branch is absent (#1424)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    git push -q origin --delete sync/issue-mirror

    run _run_block "$block"
    assert_success
    run _out
    assert_line 'eligible=false'
}

@test "fold staging fails loudly on a path commas cannot represent (#1502)" {
    block="$BATS_TEST_TMPDIR/stage.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    # FILE_PATHS is comma-separated, so a comma in a path is unrepresentable.
    # Mis-splitting it would drop or invent paths silently — the #1502 shape.
    git checkout -q -B mirror-comma origin/sync/issue-mirror
    printf 'oops\n' >"docs/issues/issue-3,4.md"
    git add -A
    git commit -qm "chore: comma path"
    git push -q -f origin HEAD:refs/heads/sync/issue-mirror
    git checkout -q -B release/1.2.3 origin/release/1.2.3

    run _run_block "$block"
    assert_failure
    assert_output --partial 'comma'
}

# ── the fold post-condition (#1502) ───────────────────────────────────────────

@test "post-fold verification fails when the fold committed nothing (#1502)" {
    stage="$BATS_TEST_TMPDIR/stage.sh"
    verify="$BATS_TEST_TMPDIR/verify.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$stage"
    _extract_run "$RELEASE_CORE" "Re-pull release branch and verify the fold landed" >"$verify"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    _run_block "$stage" >/dev/null

    # The #1502 symptom exactly: staging computed a non-empty path list,
    # commit-action reported success, and the release branch never moved.
    run _run_block "$verify" VERSION=1.2.3
    assert_failure
    assert_output --partial 'docs/issues/issue-2.md'
}

@test "post-fold verification passes once the archive landed (#1502)" {
    stage="$BATS_TEST_TMPDIR/stage.sh"
    verify="$BATS_TEST_TMPDIR/verify.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$stage"
    _extract_run "$RELEASE_CORE" "Re-pull release branch and verify the fold landed" >"$verify"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    _run_block "$stage" >/dev/null
    _commit_fold

    run _run_block "$verify" VERSION=1.2.3
    assert_success
    # A release-branch path the mirror lacks (last release's `issue-1.md`,
    # renamed away on the mirror) is tolerated: commit-action only adds and
    # updates, so deletions never propagate and the archive only grows.
    assert [ -f docs/issues/issue-1.md ]
}

# ── the promote-time reset guard (#1503) ──────────────────────────────────────

@test "mirror reset is refused when main lacks the archive (#1503)" {
    block="$BATS_TEST_TMPDIR/guard.sh"
    _extract_run "$PROMOTE" "Verify main carries the mirror archive" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"

    # main is the pre-fold state: the mirror's snapshots exist NOWHERE else.
    # Force-resetting the mirror onto it would delete them (#1502 x #1503).
    run _run_block "$block"
    assert_success
    assert_output --partial '::warning::'
    run _out
    assert_line 'safe=false'
}

@test "mirror reset proceeds when main carries the archive (#1503)" {
    stage="$BATS_TEST_TMPDIR/stage.sh"
    block="$BATS_TEST_TMPDIR/guard.sh"
    _extract_run "$RELEASE_CORE" "Stage sync mirror archive for fold" >"$stage"
    _extract_run "$PROMOTE" "Verify main carries the mirror archive" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    # The healthy sequence: the release folded the archive in and the release
    # PR merged, so main carries every path the mirror holds.
    _run_block "$stage" >/dev/null
    _commit_fold
    git push -q origin HEAD:refs/heads/main

    run _run_block "$block"
    assert_success
    refute_output --partial '::warning::'
    run _out
    assert_line 'safe=true'
    assert_line --partial 'main_sha='
}

@test "mirror reset is refused when the mirror branch is absent (#1503)" {
    block="$BATS_TEST_TMPDIR/guard.sh"
    _extract_run "$PROMOTE" "Verify main carries the mirror archive" >"$block"
    _mk_fixture "$BATS_TEST_TMPDIR/fx"
    git push -q origin --delete sync/issue-mirror

    run _run_block "$block"
    assert_success
    run _out
    assert_line 'safe=false'
}
