#!/usr/bin/env bats
# BATS tests for the scaffolded .devcontainer/scripts/init-precommit.sh
#
# The script installs the git-hook environment on container init. It must derive
# the project root from its own location, not a hard-coded /workspace/<name>
# path, so it works regardless of where the workspace is mounted (#854).

setup() {
    load test_helper
    INIT_PRECOMMIT_SH="$PROJECT_ROOT/assets/workspace/.devcontainer/scripts/init-precommit.sh"
}

@test "init-precommit.sh does not hard-code /workspace/{{SHORT_NAME}} (#854)" {
    run grep -F '/workspace/{{SHORT_NAME}}' "$INIT_PRECOMMIT_SH"
    assert_failure
}

@test "init-precommit.sh derives the project root from its own location (#854)" {
    run grep -q 'BASH_SOURCE' "$INIT_PRECOMMIT_SH"
    assert_success
}

@test "init-precommit.sh runs prek from a root at an arbitrary mount point (#854)" {
    # Reproduce the on-disk layout: <root>/.devcontainer/scripts/init-precommit.sh
    root="$BATS_TEST_TMPDIR/some/other/mount/proj"
    mkdir -p "$root/.devcontainer/scripts"
    cp "$INIT_PRECOMMIT_SH" "$root/.devcontainer/scripts/init-precommit.sh"
    printf 'repos: []\n' > "$root/.pre-commit-config.yaml"

    # Stub prek: record the CWD it is invoked from.
    stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    cat > "$stub/prek" <<EOF
#!/usr/bin/env bash
pwd > "$BATS_TEST_TMPDIR/prek-cwd"
exit 0
EOF
    chmod +x "$stub/prek"

    run env PATH="$stub:$PATH" bash "$root/.devcontainer/scripts/init-precommit.sh"
    assert_success
    assert_output --partial "Git hooks installed successfully"
    # prek ran with the derived project root as CWD (resolve symlinks for macOS /tmp)
    run cat "$BATS_TEST_TMPDIR/prek-cwd"
    assert_output "$(cd "$root" && pwd -P)"
}

@test "init-precommit.sh skips cleanly when no config is present (#854)" {
    root="$BATS_TEST_TMPDIR/noconfig/proj"
    mkdir -p "$root/.devcontainer/scripts"
    cp "$INIT_PRECOMMIT_SH" "$root/.devcontainer/scripts/init-precommit.sh"
    run bash "$root/.devcontainer/scripts/init-precommit.sh"
    assert_success
    assert_output --partial "skipping"
}
