#!/usr/bin/env bats
# #1480: `install.sh --force` is not atomic. The template rsync in
# init-workspace.sh replaces .vig-os and the root .gitignore with template
# content whose values (mode, identity, feature opt-outs, consumer gitignore
# sections) are only refilled hundreds of lines later — and .vig-os is the
# INPUT of the very next --force run, so an abort inside that window persisted
# a blanked manifest the consumer never chose.
#
# These tests EXECUTE the real script and abort it inside the torn window (the
# VIG_OS_VERSION validation exit, which sits between the copy and the late
# write-back), then assert the pre-run files come back byte-for-byte and the
# failure names what was restored.
#
# Companion (#1480 suggestion 3): the u+w permission sweep is scoped to
# template-derived paths, so a consumer's .git objects and build trees
# (target/, node_modules) are never walked or touched.

setup() {
    load test_helper
    INIT_WORKSPACE_SH="$PROJECT_ROOT/assets/init-workspace.sh"
}

# Run the real script against $2 in mode $1; extra env pairs come after.
_run_init() {
    local mode="$1" ws="$2"
    shift 2
    local stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/uv"
    chmod +x "$stub/just" "$stub/uv"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        "$@" \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode "$mode"
}

# 'not a version!' fails the ^[A-Za-z0-9._-]+$ pin validation AFTER the copy
# has replaced .vig-os/.gitignore and BEFORE the write-backs refill them —
# a real, deterministic in-window abort (no stubs, no signals).
_upgrade_aborting_in_window() {
    _run_init both "$1" VIG_OS_VERSION='not a version!'
}

@test "an in-window abort restores .vig-os and .gitignore byte-for-byte (#1480)" {
    ws="$BATS_TEST_TMPDIR/e2e-1480-restore"
    mkdir -p "$ws"
    run _run_init both "$ws"
    assert_success

    # Consumer state the template ships empty: exactly what the field failure
    # blanked (mode/identity land earlier; the opt-outs went unnoticed longest).
    sed -i 's#^DEVKIT_FEATURES_DISABLED=.*#DEVKIT_FEATURES_DISABLED=skills,worktree#' "$ws/.vig-os"
    sed -i 's#^DEVKIT_TAG_PREFIX=.*#DEVKIT_TAG_PREFIX=v#' "$ws/.vig-os"
    printf '/target/\nresult\n' >>"$ws/.gitignore"
    cp "$ws/.vig-os" "$BATS_TEST_TMPDIR/manifest.before"
    cp "$ws/.gitignore" "$BATS_TEST_TMPDIR/gitignore.before"

    run _upgrade_aborting_in_window "$ws"
    assert_failure
    assert_output --partial "Restored the pre-run"
    assert_output --partial ".vig-os"

    run cmp "$ws/.vig-os" "$BATS_TEST_TMPDIR/manifest.before"
    assert_success
    run cmp "$ws/.gitignore" "$BATS_TEST_TMPDIR/gitignore.before"
    assert_success
}

@test "a restored workspace upgrades cleanly on the retry (#1480)" {
    # The field recovery: after the failed run, a plain retry must succeed and
    # keep the consumer's opt-outs — the restored manifest is a valid input.
    ws="$BATS_TEST_TMPDIR/e2e-1480-retry"
    mkdir -p "$ws"
    run _run_init both "$ws"
    assert_success
    sed -i 's#^DEVKIT_FEATURES_DISABLED=.*#DEVKIT_FEATURES_DISABLED=skills,worktree#' "$ws/.vig-os"
    run _upgrade_aborting_in_window "$ws"
    assert_failure

    run _run_init both "$ws"
    assert_success
    run grep -x 'DEVKIT_FEATURES_DISABLED=skills,worktree' "$ws/.vig-os"
    assert_success
    run test -e "$ws/.claude/skills/tdd"
    assert_failure
}

@test "a fresh-scaffold abort still exits loudly without a pre-image (#1480)" {
    # No .vig-os/.gitignore existed before the run, so there is nothing to
    # restore — the guard must not mask the failure or die itself (set -e
    # inside the trap), and the half-applied warning still prints.
    ws="$BATS_TEST_TMPDIR/e2e-1480-fresh"
    mkdir -p "$ws"
    run _upgrade_aborting_in_window "$ws"
    assert_failure
    assert_output --partial "half-applied"
    refute_output --partial "Restored the pre-run"
}

@test "the u+w sweep never touches consumer .git or build trees (#1480)" {
    # The blanket `chmod -R u+w $WORKSPACE_DIR` walked the consumer's entire
    # workspace — .git object packs are deliberately 0444, and a multi-GB
    # target/ is both slow and a surface for the transient fts walk failures
    # that caused the field abort. The sweep is keyed on the template tree.
    ws="$BATS_TEST_TMPDIR/e2e-1480-chmod-scope"
    mkdir -p "$ws"
    run _run_init both "$ws"
    assert_success

    mkdir -p "$ws/.git/objects/pack" "$ws/target/debug"
    printf 'x' >"$ws/.git/objects/pack/pack-feed.pack"
    printf 'x' >"$ws/target/debug/artifact"
    chmod 0444 "$ws/.git/objects/pack/pack-feed.pack" "$ws/target/debug/artifact"

    run _run_init both "$ws"
    assert_success
    run stat -c '%a' "$ws/.git/objects/pack/pack-feed.pack"
    assert_output "444"
    run stat -c '%a' "$ws/target/debug/artifact"
    assert_output "444"
}

@test "template-derived scaffold files still end up user-writable (#1480)" {
    # The scoping must not regress the sweep's purpose: store-inherited 0444
    # modes on freshly copied scaffold files are lifted so the placeholder
    # substitution (and the consumer's own edits) keep working.
    ws="$BATS_TEST_TMPDIR/e2e-1480-still-writable"
    mkdir -p "$ws"
    run _run_init both "$ws"
    assert_success
    run test -w "$ws/.vig-os"
    assert_success
    run test -w "$ws/.github/workflows/ci.yml"
    assert_success
}
