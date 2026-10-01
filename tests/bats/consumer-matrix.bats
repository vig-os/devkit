#!/usr/bin/env bats
# BATS tests for scripts/consumer-matrix/render-cell.sh (#1762): the cell list
# the CI job loops over, and each cell's seed -> rendered .vig-os contract. The
# gates themselves run in CI's consumer-matrix job; here only the cheap,
# hermetic half is pinned (no prek, no zizmor, no network).

bats_require_minimum_version 1.5.0

setup() {
    load test_helper
    RENDER_CELL="$PROJECT_ROOT/scripts/consumer-matrix/render-cell.sh"
    # init-workspace.sh ends with `just sync` in devcontainer/both modes; stub
    # just, as init-workspace.bats does, so a render stays hermetic.
    STUB_BIN="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$STUB_BIN"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$STUB_BIN/just"
    chmod +x "$STUB_BIN/just"
}

# Value of KEY $2 in the .vig-os of workspace $1 (empty when absent).
_manifest() {
    sed -n "s/^$2=//p" "$1/.vig-os"
}

@test "list prints exactly the MVP cells, one per line" {
    run "$RENDER_CELL" list
    assert_success
    assert_output "$(printf '%s\n' direnv devcontainer bare trunk \
        features-disabled ci-runner tag-prefix language-guard)"
}

@test "an unknown cell is refused, naming the known cells" {
    run "$RENDER_CELL" seed no-such-cell
    assert_failure
    assert_output --partial "unknown cell 'no-such-cell'"
    assert_output --partial "language-guard"
}

@test "mode and workflow cells pre-seed nothing" {
    local cell
    for cell in direnv devcontainer bare trunk; do
        run "$RENDER_CELL" seed "$cell"
        assert_success
        assert_output ""
    done
}

@test "features-disabled seeds every feature group init-workspace.sh knows" {
    local valid
    valid="$(sed -n 's/^VALID_FEATURES=(\(.*\))$/\1/p' "$PROJECT_ROOT/assets/init-workspace.sh" | tr ' ' ',')"
    [[ -n "$valid" ]]
    run "$RENDER_CELL" seed features-disabled
    assert_success
    assert_output "DEVKIT_FEATURES_DISABLED=$valid"
}

@test "knob cells seed their knob" {
    run "$RENDER_CELL" seed ci-runner
    assert_output "DEVKIT_CI_RUNNER=self-hosted,linux,x64,consumer-matrix"
    run "$RENDER_CELL" seed tag-prefix
    assert_output "DEVKIT_TAG_PREFIX=v"
    run "$RENDER_CELL" seed language-guard
    assert_output "DEVKIT_LANGUAGES=python"
}

@test "every seeded knob survives a first-scaffold render into .vig-os" {
    local cell ws line
    for cell in features-disabled ci-runner tag-prefix language-guard; do
        ws="$BATS_TEST_TMPDIR/$cell"
        PATH="$STUB_BIN:$PATH" run "$RENDER_CELL" render "$cell" "$ws"
        assert_success
        assert_equal "$(_manifest "$ws" DEVKIT_MODE)" both
        while IFS= read -r line; do
            run grep -qxF -- "$line" "$ws/.vig-os"
            assert_success
        done < <("$RENDER_CELL" seed "$cell")
    done
}

@test "language-guard renders a declared language with no marker file (#1466)" {
    local ws="$BATS_TEST_TMPDIR/language-guard"
    PATH="$STUB_BIN:$PATH" run "$RENDER_CELL" render language-guard "$ws"
    assert_success
    assert_equal "$(_manifest "$ws" DEVKIT_LANGUAGES)" python
    assert_file_not_exists "$ws/pyproject.toml"
}

@test "mode cells render their mode; trunk renders the trunk model in both mode" {
    local cell ws
    for cell in direnv devcontainer bare; do
        ws="$BATS_TEST_TMPDIR/$cell"
        PATH="$STUB_BIN:$PATH" run "$RENDER_CELL" render "$cell" "$ws"
        assert_success
        assert_equal "$(_manifest "$ws" DEVKIT_MODE)" "$cell"
        assert_equal "$(_manifest "$ws" DEVKIT_WORKFLOW)" ""
    done
    # `both`, not direnv: direnv ships no .pre-commit-config.yaml, so only a
    # mode with the scaffolded hook config runs the trunk branch guard.
    ws="$BATS_TEST_TMPDIR/trunk"
    PATH="$STUB_BIN:$PATH" run "$RENDER_CELL" render trunk "$ws"
    assert_success
    assert_equal "$(_manifest "$ws" DEVKIT_MODE)" both
    assert_equal "$(_manifest "$ws" DEVKIT_WORKFLOW)" trunk
    assert_file_exists "$ws/.pre-commit-config.yaml"
}

@test "render refuses a non-empty workspace" {
    local ws="$BATS_TEST_TMPDIR/busy"
    mkdir -p "$ws"
    touch "$ws/keep"
    run "$RENDER_CELL" render direnv "$ws"
    assert_failure
    assert_output --partial "refusing to render into non-empty"
}
