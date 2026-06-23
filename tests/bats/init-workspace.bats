#!/usr/bin/env bats
# BATS tests for init-workspace.sh
#
# Tests script structure (executable, shebang, strict mode).

setup() {
    load test_helper
    INIT_WORKSPACE_SH="$PROJECT_ROOT/assets/init-workspace.sh"
    PARSE_GITHUB_REMOTE_LIB="$PROJECT_ROOT/assets/parse-github-remote-lib.sh"
    TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace"
}

# ── Claude-native template scaffold (#629) ────────────────────────────────────
# init-workspace.sh rsyncs assets/workspace/ verbatim into a new workspace, so
# asserting on the template tree is a faithful, build-free proxy for "what new
# workspaces scaffold".

@test "template scaffolds .claude/ directory" {
    run test -d "$TEMPLATE_DIR/.claude"
    assert_success
}

@test "template scaffolds .claude/skills/" {
    run test -d "$TEMPLATE_DIR/.claude/skills"
    assert_success
}

@test "template does NOT scaffold .cursor/ directory" {
    run test -e "$TEMPLATE_DIR/.cursor"
    assert_failure
}

@test "template carries no Cursor editor glue (#629 scope)" {
    # #629 owns: the cursor-remote-ssh socket glob and the `command -v cursor`
    # editor launch. The remaining `cursor-agent` worktree-pipeline references
    # are owned by #627; the AI blocklist's "cursor" entries by #630.
    # Exclude CHANGELOG.md: released/Unreleased prose legitimately names the
    # removed glue when describing the change.
    run grep -rn --exclude=CHANGELOG.md \
        'cursor-remote\|command -v cursor' "$TEMPLATE_DIR"
    assert_failure
}

# ── direnv / flake stub (#640) ────────────────────────────────────────────────
# The downstream minimal flake stub + .envrc let a new repo `direnv allow` /
# `nix develop` into the shared toolchain. They are never-overwritten on
# upgrade (the user owns the extraPackages block).

@test "template scaffolds the downstream flake.nix stub (#640)" {
    run test -f "$TEMPLATE_DIR/flake.nix"
    assert_success
}

@test "template scaffolds the .envrc (use flake) stub (#640)" {
    run test -f "$TEMPLATE_DIR/.envrc"
    assert_success
}

@test "downstream flake stub consumes the vigos toolchain SSoT (#640)" {
    run grep -q 'vigos.lib.mkProjectShell' "$TEMPLATE_DIR/flake.nix"
    assert_success
    run grep -q 'vigos/nixpkgs' "$TEMPLATE_DIR/flake.nix"
    assert_success
}

@test "flake.nix and .envrc are preserved on --force upgrade (#640)" {
    # shellcheck disable=SC2016
    run grep -E '"flake\.nix"' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    run grep -E '"\.envrc"' "$INIT_WORKSPACE_SH"
    assert_success
}

# ── delivery-mode picker (#641) ───────────────────────────────────────────────
# init-workspace.sh scaffolds the template, then prunes to the chosen mode:
#   devcontainer -> .devcontainer/ only (no flake.nix/.envrc)
#   direnv       -> flake.nix + .envrc only (no .devcontainer/)
#   both         -> everything (default, current behaviour)
# We exercise the prune on a copy of the template (build-free proxy for the
# in-container scaffold), and assert the flag/default wiring on script structure.

# Apply the same prune the script does for a given mode to $1 (a workspace copy).
prune_mode() {
    local ws="$1" mode="$2"
    case "$mode" in
        devcontainer) rm -f "$ws/flake.nix" "$ws/.envrc" ;;
        direnv) rm -rf "$ws/.devcontainer" ;;
        both) : ;;
    esac
}

@test "mode=devcontainer keeps .devcontainer/, drops flake.nix and .envrc (#641)" {
    ws="$BATS_TEST_TMPDIR/ws-devcontainer"
    cp -r "$TEMPLATE_DIR" "$ws"
    prune_mode "$ws" devcontainer
    run test -d "$ws/.devcontainer"
    assert_success
    run test -e "$ws/flake.nix"
    assert_failure
    run test -e "$ws/.envrc"
    assert_failure
}

@test "mode=direnv keeps flake.nix and .envrc, drops .devcontainer/ (#641)" {
    ws="$BATS_TEST_TMPDIR/ws-direnv"
    cp -r "$TEMPLATE_DIR" "$ws"
    prune_mode "$ws" direnv
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/.envrc"
    assert_success
    run test -e "$ws/.devcontainer"
    assert_failure
}

@test "mode=both keeps .devcontainer/, flake.nix and .envrc (#641)" {
    ws="$BATS_TEST_TMPDIR/ws-both"
    cp -r "$TEMPLATE_DIR" "$ws"
    prune_mode "$ws" both
    run test -d "$ws/.devcontainer"
    assert_success
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/.envrc"
    assert_success
}

@test "init-workspace.sh accepts a --mode flag (#641)" {
    run grep -- '--mode' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh validates --mode against the three modes (#641)" {
    run grep -E 'devcontainer\|direnv\|both' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh defaults to 'both' under --no-prompts (#641)" {
    # shellcheck disable=SC2016
    run grep -A4 'if \[\[ -z "\$MODE" \]\]' "$INIT_WORKSPACE_SH"
    assert_success
    assert_output --partial 'MODE="both"'
}

@test "init-workspace.sh prunes the scaffold by delivery mode (#641)" {
    # devcontainer drops the flake stub; direnv drops the devcontainer scaffold.
    # shellcheck disable=SC2016
    run grep -A12 'case "\$MODE" in' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'rm -f "$WORKSPACE_DIR/flake.nix" "$WORKSPACE_DIR/.envrc"'
    # shellcheck disable=SC2016
    assert_output --partial 'rm -rf "$WORKSPACE_DIR/.devcontainer"'
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
