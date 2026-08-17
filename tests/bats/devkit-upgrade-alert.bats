#!/usr/bin/env bats
# BATS tests for the devkit-upgrade failure report (#1530).
#
# tests/test_workflow_devkit_upgrade.py pins that the `report` job is WIRED —
# the result gate, the issues-scoped mint, the env plumbing. It cannot pin that
# the legs BEHAVE: that a second weekly failure comments instead of filing issue
# number two, that a green run closes the one that is open, and that a missing
# App grant is a warning rather than a red run. That branching is the whole
# feature, so it is executed here.
#
# Same idiom as release-mirror-fold.bats: the rendered `run:` block is extracted
# from the shipped workflow and run against a stub `gh` — real bash, real jq,
# no network and no GitHub.

setup() {
    load test_helper
    WF="$PROJECT_ROOT/assets/workspace/.github/workflows/devkit-upgrade.yml"
    FAIL_LEG="$BATS_TEST_TMPDIR/fail.sh"
    CLOSE_LEG="$BATS_TEST_TMPDIR/close.sh"
    STUBS="$BATS_TEST_TMPDIR/stubs"
    GH_LOG="$BATS_TEST_TMPDIR/gh.log"
    GH_ISSUES="$BATS_TEST_TMPDIR/issues.json"
    GH_JOBS="$BATS_TEST_TMPDIR/jobs.txt"
    RUN_URL="https://github.example/test/repo/actions/runs/42"
    mkdir -p "$STUBS"
    : >"$GH_LOG"
    printf '[]\n' >"$GH_ISSUES"
    : >"$GH_JOBS"
    _extract_run "$WF" "File or update the upgrade-failure issue" >"$FAIL_LEG"
    _extract_run "$WF" "Close the upgrade-failure issue" >"$CLOSE_LEG"
    _stub_gh
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

# Stub gh: records every invocation and answers the three calls the legs make.
# `api` returns the value a real `--jq` filter would print (the stub cannot run
# the filter); `issue list` returns raw JSON, which the leg pipes into real jq.
_stub_gh() {
    cat >"$STUBS/gh" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GH_LOG"
case "${1:-} ${2:-}" in
    "api "*)          cat "$GH_JOBS" ;;
    "issue list")     cat "$GH_ISSUES" ;;
    "issue create")   echo "https://github.example/test/repo/issues/7" ;;
esac
exit 0
STUB
    chmod +x "$STUBS/gh"
}

# Run an extracted leg. Extra args are `NAME=value` step env vars.
_run_leg() {
    local block="$1"
    shift
    env PATH="$STUBS:$PATH" \
        GH_LOG="$GH_LOG" GH_ISSUES="$GH_ISSUES" GH_JOBS="$GH_JOBS" \
        GH_REPO=test/repo RUN_TOKEN=run-token RUN_URL="$RUN_URL" \
        GITHUB_REPOSITORY=test/repo GITHUB_RUN_ID=42 \
        "$@" bash "$block"
}

_log() { cat "$GH_LOG"; }

# One open issue carrying the tracker's body marker.
_open_tracker() {
    cat >"$GH_ISSUES" <<'JSON'
[{"number": 3, "body": "history\n<!-- devkit-upgrade-failure -->\nmore"}]
JSON
}

# ── the failure leg ───────────────────────────────────────────────────────────

@test "failure leg files a tracking issue when none is open (#1530)" {
    run _run_leg "$FAIL_LEG" GH_TOKEN=app-token CURRENT=1.9.0 TARGET=1.11.0
    assert_success

    run _log
    assert_output --partial 'issue create'
    assert_output --partial 'chore(devkit): automated devkit upgrade is failing'
    # The marker is what the next run and the close leg key on.
    assert_output --partial '<!-- devkit-upgrade-failure -->'
    assert_output --partial "$RUN_URL"
    refute_output --partial 'issue comment'
}

@test "failure leg re-uses the open tracking issue (#1530)" {
    _open_tracker

    run _run_leg "$FAIL_LEG" GH_TOKEN=app-token CURRENT=1.9.0 TARGET=1.11.0
    assert_success
    assert_output --partial '#3'

    # At most one open tracker per repo: a repeat failure comments on it.
    run _log
    assert_output --partial 'issue comment 3'
    refute_output --partial 'issue create'
}

@test "failure leg ignores an unrelated open issue (#1530)" {
    printf '[{"number": 9, "body": "a human wrote this"}]\n' >"$GH_ISSUES"

    run _run_leg "$FAIL_LEG" GH_TOKEN=app-token CURRENT=1.9.0 TARGET=1.11.0
    assert_success

    run _log
    assert_output --partial 'issue create'
    refute_output --partial 'issue comment'
}

@test "failure leg names the failing step and both versions (#1530)" {
    printf 'Commit the upgrade in the project shell\n' >"$GH_JOBS"

    run _run_leg "$FAIL_LEG" GH_TOKEN=app-token CURRENT=1.9.0 TARGET=1.11.0
    assert_success

    run _log
    assert_output --partial 'Commit the upgrade in the project shell'
    assert_output --partial '1.9.0'
    assert_output --partial '1.11.0'
}

@test "failure leg reports an unresolved target as unknown (#1530)" {
    # The resolve step itself failed: no target, and possibly no pin either.
    run _run_leg "$FAIL_LEG" GH_TOKEN=app-token CURRENT= TARGET=
    assert_success

    run _log
    assert_output --partial 'unknown'
    assert_output --partial 'Failing step: unknown'
}

@test "failure leg warns instead of failing without the Issues grant (#1530)" {
    # The mint is continue-on-error, so an installation that never received the
    # Issues grant reaches this leg with an empty token. Reporting may never
    # break the upgrade path it reports on.
    run _run_leg "$FAIL_LEG" GH_TOKEN= CURRENT=1.9.0 TARGET=1.11.0
    assert_success
    assert_output --partial '::warning::'

    run _log
    refute_output --partial 'issue'
}

# ── the success leg ───────────────────────────────────────────────────────────

@test "success leg closes the open tracking issue (#1530)" {
    _open_tracker

    run _run_leg "$CLOSE_LEG" GH_TOKEN=app-token
    assert_success
    assert_output --partial '#3'

    run _log
    assert_output --partial 'issue close 3'
    assert_output --partial "$RUN_URL"
}

@test "success leg is a clean no-op when nothing is open (#1530)" {
    run _run_leg "$CLOSE_LEG" GH_TOKEN=app-token
    assert_success

    run _log
    refute_output --partial 'issue close'
}

@test "success leg no-ops without the Issues grant (#1530)" {
    _open_tracker

    run _run_leg "$CLOSE_LEG" GH_TOKEN=
    assert_success

    run _log
    refute_output --partial 'issue close'
}
