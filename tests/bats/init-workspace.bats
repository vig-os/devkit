#!/usr/bin/env bats
# BATS tests for init-workspace.sh
#
# Tests script structure (executable, shebang, strict mode).

setup() {
    load test_helper
    INIT_WORKSPACE_SH="$PROJECT_ROOT/assets/init-workspace.sh"
    PARSE_GITHUB_REMOTE_LIB="$PROJECT_ROOT/assets/parse-github-remote-lib.sh"
}

# ── script structure ──────────────────────────────────────────────────────────

@test "init-workspace.sh is executable" {
    run test -x "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh has shebang" {
    run head -1 "$INIT_WORKSPACE_SH"
    assert_output "#!/bin/bash"
}

@test "init-workspace.sh uses strict error handling (set -euo pipefail)" {
    run grep 'set -euo pipefail' "$INIT_WORKSPACE_SH"
    assert_success
}

# ── idempotent rename guard (#197) ───────────────────────────────────────────

@test "init-workspace.sh guards against nested template_project on re-run" {
    run grep -A4 'if \[\[ -d.*src/template_project' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'src/${SHORT_NAME}'
    assert_output --partial 'rm -rf'
}

@test "init-workspace.sh uses rsync without fallback" {
    run grep 'rsync -av' "$INIT_WORKSPACE_SH"
    assert_success

    run grep 'if command -v rsync' "$INIT_WORKSPACE_SH"
    assert_failure
}

@test "init-workspace.sh excludes preserved files only when they exist" {
    # shellcheck disable=SC2016
    run grep -A3 'for preserved in "${PRESERVE_FILES\[@\]}"' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'if [[ -e "$WORKSPACE_DIR/$preserved" ]]; then'
    # shellcheck disable=SC2016
    assert_output --partial 'EXCLUDE_ARGS+=("--exclude=$preserved")'
}

@test "init-workspace.sh accepts --smoke-test flag" {
    run grep -- '--smoke-test' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh uses SCRIPT_DIR smoke-test assets path" {
    # shellcheck disable=SC2016
    run grep 'SMOKE_TEST_DIR="$SCRIPT_DIR/smoke-test"' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh smoke mode implies --no-prompts" {
    # shellcheck disable=SC2016
    run grep -A4 'if \[\[ "\$SMOKE_TEST" == "true" \]\]' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'NO_PROMPTS=true'
}

@test "init-workspace.sh smoke mode implies --force" {
    # shellcheck disable=SC2016
    run grep -A4 'if \[\[ "\$SMOKE_TEST" == "true" \]\]' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'FORCE=true'
}

@test "init-workspace.sh smoke mode uses rsync --delete for clean deploy" {
    run grep 'rsync -av --delete' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh smoke mode excludes synced docs directories from delete" {
    run grep -A1 'rsync -av --delete' "$INIT_WORKSPACE_SH"
    assert_success
    assert_output --partial "--exclude='docs/issues/'"
    assert_output --partial "--exclude='docs/pull-requests/'"
}

# ── parse-github-remote-lib (#509) ─────────────────────────────────────────

@test "parse_github_remote parses HTTPS github.com URL" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'https://github.com/org/repo.git'"
    assert_success
    assert_output "org/repo"
}

@test "parse_github_remote parses HTTPS URL with trailing slash" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'https://github.com/org/repo/'"
    assert_success
    assert_output "org/repo"
}

@test "parse_github_remote parses git@github.com SSH URL" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'git@github.com:acme/widget.git'"
    assert_success
    assert_output "acme/widget"
}

@test "parse_github_remote parses ssh://git@github.com URL" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'ssh://git@github.com/foo/bar.git'"
    assert_success
    assert_output "foo/bar"
}

@test "parse_github_remote fails for non-GitHub URL" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'https://gitlab.com/a/b.git'"
    assert_failure
}

@test "parse_github_remote rejects owner/repo outside GitHub slug charset" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && parse_github_remote 'https://github.com/or;g/re\$po.git'"
    assert_failure
}

@test "resolve_github_repository uses GITHUB_REPOSITORY when set" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && GITHUB_REPOSITORY=vig-os/app resolve_github_repository"
    assert_success
    assert_output --partial "vig-os/app (from environment)"
}

@test "resolve_github_repository rejects invalid GITHUB_REPOSITORY from environment" {
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && GITHUB_REPOSITORY='bad repo/name' NO_PROMPTS=true resolve_github_repository"
    assert_failure
    assert_output --partial "GITHUB_REPOSITORY must be owner/repo"
}

@test "resolve_github_repository parses origin from git workspace" {
    git_fixture=$(mktemp -d)
    git init -q "$git_fixture"
    git -C "$git_fixture" remote add origin https://github.com/acme/widget.git
    # CI sets GITHUB_REPOSITORY (e.g. vig-os/devcontainer); clear it so origin is used.
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && GITHUB_REPOSITORY= WORKSPACE_DIR=\"$git_fixture\" NO_PROMPTS=true resolve_github_repository"
    assert_success
    assert_output --partial "acme/widget (from git remote origin)"
    rm -rf "$git_fixture"
}

@test "resolve_github_repository fails no-prompts without github.com origin" {
    git_fixture=$(mktemp -d)
    git init -q "$git_fixture"
    git -C "$git_fixture" remote add origin https://gitlab.com/x/y.git
    # CI sets GITHUB_REPOSITORY; clear it so non-GitHub origin is exercised.
    run bash -c "source \"$PARSE_GITHUB_REMOTE_LIB\" && GITHUB_REPOSITORY= WORKSPACE_DIR=\"$git_fixture\" NO_PROMPTS=true resolve_github_repository"
    assert_failure
    rm -rf "$git_fixture"
}

@test "init-workspace.sh sources parse-github-remote-lib.sh" {
    # shellcheck disable=SC2016
    pattern='source "$SCRIPT_DIR/parse-github-remote-lib.sh"'
    run grep -F "$pattern" "$INIT_WORKSPACE_SH"
    assert_success
}
