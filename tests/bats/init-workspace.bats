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

# ── opt-in local dev services (#795) ─────────────────────────────────────────
# mkProjectServices (process-compose + services-flake) is opt-in for consumers:
# the flake stub documents the wiring in a commented block, and justfile.project
# ships a commented `services` recipe. Both files are preserved on upgrade, so
# existing consumers are untouched by construction.

@test "downstream flake stub documents the opt-in mkProjectServices block (#795)" {
    run grep -q 'vigos.lib.mkProjectServices' "$TEMPLATE_DIR/flake.nix"
    assert_success
    run grep -q 'nix run .#services' "$TEMPLATE_DIR/flake.nix"
    assert_success
}

@test "justfile.project ships the commented opt-in services recipe (#795)" {
    run grep -q 'nix run .#services' "$TEMPLATE_DIR/justfile.project"
    assert_success
}

@test "devcontainer verbs carry the devc- prefix, freeing generic names (#795)" {
    # The compose-stack verbs are namespaced devc-* so a services verb (and
    # future generic verbs) cannot collide with them. Guard both directions:
    # devc-up exists, bare `up:`/`down:` recipes do not.
    run grep -qE '^devc-up:' "$TEMPLATE_DIR/.devcontainer/justfile.devc"
    assert_success
    run grep -qE '^(up|down|status|logs|shell|restart|open) *[a-z*]*:' \
        "$TEMPLATE_DIR/.devcontainer/justfile.devc"
    assert_failure
}

# ── justfile audit (#806) ─────────────────────────────────────────────────────
# Post-#795 completion of the devc-* namespacing, and the worktree recipes are
# reachable in consumers (the scaffold ships justfile.worktree AND .claude
# skills that invoke `just worktree-start`, so the root justfile must import it).

@test "remaining devcontainer verbs are devc-namespaced: check + upgrade (#806)" {
    run grep -qE '^devc-check' "$TEMPLATE_DIR/.devcontainer/justfile.devc"
    assert_success
    run grep -qE '^devc-upgrade:' "$TEMPLATE_DIR/.devcontainer/justfile.devc"
    assert_success
    run grep -qE '^(check|devcontainer-upgrade) *[a-z*]*:' \
        "$TEMPLATE_DIR/.devcontainer/justfile.devc"
    assert_failure
}

@test "scaffold justfile imports the shipped worktree recipes (#806)" {
    run grep -qF "import? '.devcontainer/justfile.worktree'" "$TEMPLATE_DIR/justfile"
    assert_success
}

@test "scaffold devcontainer README documents the live compose layering (#806)" {
    # The override-file workflow was replaced by docker-compose.project.yaml /
    # docker-compose.local.yaml; the shipped README must not resurrect it.
    run grep -q 'docker-compose.override' "$TEMPLATE_DIR/.devcontainer/README.md"
    assert_failure
    run grep -q 'docker-compose.project.yaml' "$TEMPLATE_DIR/.devcontainer/README.md"
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
    # devcontainer drops the flake stub (unless pre-existing, #859); direnv
    # drops the devcontainer scaffold.
    # shellcheck disable=SC2016
    run grep -A28 'case "\$MODE" in' "$INIT_WORKSPACE_SH"
    assert_success
    # shellcheck disable=SC2016
    assert_output --partial 'rm -f "$WORKSPACE_DIR/flake.nix"'
    # shellcheck disable=SC2016
    assert_output --partial 'rm -f "$WORKSPACE_DIR/.envrc"'
    # shellcheck disable=SC2016
    assert_output --partial 'rm -rf "$WORKSPACE_DIR/.devcontainer"'
}

# ── delivery-mode scaffold, end to end (#641) ─────────────────────────────────
# The tests above assert the prune in isolation; these run init-workspace.sh
# itself (arg-parse → rsync → prune → placeholder substitution) against a temp
# workspace and assert the real scaffold. TEMPLATE_DIR/WORKSPACE_DIR are
# overridden to host paths and `just` is stubbed so the final `just sync` step
# is a fast no-op rather than a real `uv sync`.

# Run the real script in delivery mode $1, scaffolding into the empty dir $2.
_scaffold() {
    local mode="$1" ws="$2"
    local stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode "$mode"
}

@test "init-workspace --mode=devcontainer scaffolds .devcontainer only (#641)" {
    ws="$BATS_TEST_TMPDIR/e2e-devcontainer"
    mkdir -p "$ws"
    run _scaffold devcontainer "$ws"
    assert_success
    run test -d "$ws/.devcontainer"
    assert_success
    run test -e "$ws/flake.nix"
    assert_failure
    run test -e "$ws/.envrc"
    assert_failure
}

@test "init-workspace --mode=direnv scaffolds flake.nix + .envrc only (#641)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/.envrc"
    assert_success
    run test -e "$ws/.devcontainer"
    assert_failure
}

@test "init-workspace --mode=both scaffolds everything (#641)" {
    ws="$BATS_TEST_TMPDIR/e2e-both"
    mkdir -p "$ws"
    run _scaffold both "$ws"
    assert_success
    run test -d "$ws/.devcontainer"
    assert_success
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/.envrc"
    assert_success
}

@test "init-workspace --mode=direnv yields a justfile that still loads (#641)" {
    # Regression guard: direnv mode prunes .devcontainer/, so the scaffolded
    # justfile's .devcontainer imports must be optional or `just` fails to parse.
    real_just="$(command -v just)"
    ws="$BATS_TEST_TMPDIR/e2e-direnv-just"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run bash -c "cd '$ws' && '$real_just' --list"
    assert_success
}

@test "init-workspace rejects an invalid --mode (#641)" {
    ws="$BATS_TEST_TMPDIR/e2e-bad"
    mkdir -p "$ws"
    run _scaffold bogus "$ws"
    assert_failure
    assert_output --partial "Invalid --mode"
}

# ── direnv (re)scaffold must not clobber a populated consumer repo (#738) ──────
# `install.sh --mode direnv --force` on an existing project deployed the full
# template over it: overwrote a real pyproject.toml and deleted a populated
# .devcontainer/. direnv mode must only ADD the Nix/direnv stub.

@test "init-workspace --mode=direnv --force preserves a populated pyproject.toml (#738)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv-keep-pyproject"
    mkdir -p "$ws"
    printf '# SENTINEL-738 real consumer pyproject\n[project]\nname = "real_consumer"\n' \
        >"$ws/pyproject.toml"
    run _scaffold direnv "$ws"
    assert_success
    run grep -q 'SENTINEL-738 real consumer pyproject' "$ws/pyproject.toml"
    assert_success
    # ...and the Nix/direnv stub was still added.
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/.envrc"
    assert_success
}

@test "init-workspace --mode=direnv --force preserves a populated .devcontainer/ (#738)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv-keep-devcontainer"
    mkdir -p "$ws/.devcontainer"
    printf '{ "name": "SENTINEL-738 real devcontainer" }\n' \
        >"$ws/.devcontainer/devcontainer.json"
    run _scaffold direnv "$ws"
    assert_success
    run test -f "$ws/.devcontainer/devcontainer.json"
    assert_success
    run grep -q 'SENTINEL-738 real devcontainer' "$ws/.devcontainer/devcontainer.json"
    assert_success
}

# ── upgrade preview/report follows template symlinks (#949) ───────────────────
# The Nix image bakes assets/workspace as a tree of symlinks into the nix store,
# so the --preview/--force classifier's `find -type f` matched ZERO files and the
# OVERWRITTEN/ADDED report was always empty. The real copy uses `rsync -avL`
# (follows symlinks), so only the report was blind. The classifier must follow
# symlinks (find -L) to match the copy semantics.

# Build a TEMPLATE_DIR whose files are symlinks into a store-like dir (mirrors
# the baked Nix image), then run the --preview report against workspace $1 and
# echo it. `just` is stubbed so nothing external is required.
_preview_symlinked_template() {
    local ws="$1"
    local tmpl="$BATS_TEST_TMPDIR/tmpl-949"
    local store="$BATS_TEST_TMPDIR/store-949"
    mkdir -p "$tmpl" "$store"
    printf 'template overwrite body\n' >"$store/overwrite-src"
    printf 'template add body\n' >"$store/add-src"
    # Symlinked template files (as the nix store bakes them), not regular files.
    ln -s "$store/overwrite-src" "$tmpl/sentinel-overwrite.txt"
    ln -s "$store/add-src" "$tmpl/sentinel-add.txt"
    local stub="$BATS_TEST_TMPDIR/stub-bin-949"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$tmpl" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --preview --force --no-prompts --mode both
}

@test "upgrade preview lists a symlinked template file that conflicts under OVERWRITTEN (#949)" {
    ws="$BATS_TEST_TMPDIR/e2e-preview-overwrite"
    mkdir -p "$ws"
    # A workspace file the symlinked template would overwrite.
    printf 'consumer body\n' >"$ws/sentinel-overwrite.txt"
    run _preview_symlinked_template "$ws"
    assert_success
    refute_output --partial "No existing files would be overwritten"
    assert_output --partial "will be OVERWRITTEN"
    assert_output --partial "sentinel-overwrite.txt"
}

@test "upgrade preview lists a symlinked, workspace-absent template file under ADDED (#949)" {
    ws="$BATS_TEST_TMPDIR/e2e-preview-add"
    mkdir -p "$ws"
    printf 'consumer body\n' >"$ws/sentinel-overwrite.txt"
    run _preview_symlinked_template "$ws"
    assert_success
    refute_output --partial "No new files would be added"
    assert_output --partial "will be ADDED"
    assert_output --partial "sentinel-add.txt"
}

# ── upgrade preview must not over-report the baked .venv symlink tree (#951) ───
# The #949 fix switched the report classifier to `find -L`, which correctly
# follows the store-symlink template. But `find -L` also descends the baked
# .venv symlink tree, so the ADDED section listed phantom
# .venv/.../site-packages/* files the real rsync copy never writes — the copy
# excludes .git, .venv, docs/issues/ and docs/pull-requests/. The report `find`
# must mirror those static excludes so ADDED matches what the upgrade will do.

# Build a TEMPLATE_DIR that contains both a normal symlinked template file and a
# symlinked file inside a baked .venv tree (mirrors the Nix image), then run the
# --preview report against workspace $1 and echo it.
_preview_symlinked_template_venv() {
    local ws="$1"
    local tmpl="$BATS_TEST_TMPDIR/tmpl-951"
    local store="$BATS_TEST_TMPDIR/store-951"
    mkdir -p "$tmpl/.venv/lib/python3.12/site-packages" "$store"
    printf 'template add body\n' >"$store/add-src"
    printf 'phantom venv body\n' >"$store/venv-src"
    # A normal symlinked template file that must still be reported as ADDED...
    ln -s "$store/add-src" "$tmpl/sentinel-add.txt"
    # ...and a symlinked file inside the baked .venv tree that must NOT be.
    ln -s "$store/venv-src" \
        "$tmpl/.venv/lib/python3.12/site-packages/phantom-venv-pkg.py"
    local stub="$BATS_TEST_TMPDIR/stub-bin-951"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$tmpl" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --preview --force --no-prompts --mode both
}

@test "upgrade preview omits the baked .venv symlink tree from ADDED (#951)" {
    ws="$BATS_TEST_TMPDIR/e2e-preview-venv"
    mkdir -p "$ws"
    run _preview_symlinked_template_venv "$ws"
    assert_success
    # The real symlinked template file is still reported as ADDED...
    assert_output --partial "will be ADDED"
    assert_output --partial "sentinel-add.txt"
    # ...but the baked .venv tree the rsync copy excludes is not over-reported.
    refute_output --partial "phantom-venv-pkg.py"
    refute_output --partial "site-packages"
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

# ── language-neutral scaffold (#929) ─────────────────────────────────────────

@test "template ships no Python package starter (#929)" {
    # The copied scaffold is language-neutral: no pyproject.toml, src/ or
    # tests/. Python is opt-in via `nix flake init -t ...#python` (#930).
    run test -e "$TEMPLATE_DIR/pyproject.toml"
    assert_failure
    run test -e "$TEMPLATE_DIR/src"
    assert_failure
    run test -e "$TEMPLATE_DIR/tests"
    assert_failure
}

@test "init-workspace.sh no longer renames a template Python package (#929)" {
    run grep -q 'template_project' "$INIT_WORKSPACE_SH"
    assert_failure
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
    run grep 'rsync -avL --delete' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace.sh smoke mode excludes synced docs directories from delete" {
    run grep -A1 'rsync -avL --delete' "$INIT_WORKSPACE_SH"
    assert_success
    assert_output --partial "--exclude='docs/issues/'"
    assert_output --partial "--exclude='docs/pull-requests/'"
}

# ── Nix-image scaffold: real, writable files (#664) ───────────────────────────
# The Nix image bakes the template as read-only /nix/store symlinks. The scaffold
# rsync must --copy-links (-L) so a new workspace gets real files (not dangling
# symlinks on the host), and must restore writability (the store mode is 0444).

@test "init-workspace.sh dereferences store symlinks when scaffolding (#664)" {
    # Every template/asset rsync must copy referents, not symlinks.
    run grep -nE 'rsync -avL' "$INIT_WORKSPACE_SH"
    assert_success
    # ...and none may scaffold with a plain `rsync -av ` (symlinks-as-symlinks).
    run grep -nE 'rsync -av ' "$INIT_WORKSPACE_SH"
    assert_failure
}

@test "init-workspace.sh makes the scaffold user-writable (#664)" {
    # shellcheck disable=SC2016
    run grep -E 'chmod -R u\+w "\$WORKSPACE_DIR"' "$INIT_WORKSPACE_SH"
    assert_success
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

# ── .vig-os version-pin override (#852) ───────────────────────────────────────
# The image bakes the release it was built from into the scaffolded .vig-os
# (flake bootstrap), which is correct for finals but stale for release
# candidates: the repo-root pin only advances at finalize. install.sh forwards
# the explicitly requested --version as VIG_OS_VERSION so the scaffold pins the
# image actually installed.

@test "init-workspace honors VIG_OS_VERSION for the scaffolded .vig-os pin (#852)" {
    run grep -q 'VIG_OS_VERSION' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "init-workspace writes DEVCONTAINER_VERSION from the VIG_OS_VERSION override (#852)" {
    # shellcheck disable=SC2016
    run grep -F 'DEVCONTAINER_VERSION=${VIG_OS_VERSION}' "$INIT_WORKSPACE_SH"
    assert_success
}

# ── .vig-os pin from the image built-tag record (#921) ────────────────────────
# A raw `podman run ... init-workspace.sh` upgrade forwards no VIG_OS_VERSION
# (only install.sh does), so without a fallback the scaffold stays pinned to the
# baked template pin — stale for RC images. The image bakes its true built tag as
# an authoritative record (/root/assets/VERSION, VERSION_FILE); init reads it when
# no explicit override is present. VERSION_FILE/TEMPLATE_DIR/WORKSPACE_DIR are
# overridden to host paths and `just` is stubbed so `just sync` is a no-op.

# Scaffold in $mode into $ws with VERSION_FILE=$verfile and no VIG_OS_VERSION.
_scaffold_with_version_file() {
    local mode="$1" ws="$2" verfile="$3"
    local stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        VERSION_FILE="$verfile" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode "$mode"
}

@test "init-workspace stamps .vig-os from the image VERSION record when no override is set (#921)" {
    ws="$BATS_TEST_TMPDIR/e2e-921-record"
    mkdir -p "$ws"
    verfile="$BATS_TEST_TMPDIR/VERSION-record"
    printf '0.5.0-rc3\n' >"$verfile"
    run _scaffold_with_version_file bare "$ws" "$verfile"
    assert_success
    run grep '^DEVCONTAINER_VERSION=' "$ws/.vig-os"
    assert_output "DEVCONTAINER_VERSION=0.5.0-rc3"
}

@test "init-workspace leaves the baked pin untouched when no VERSION record exists (#921)" {
    ws="$BATS_TEST_TMPDIR/e2e-921-absent"
    mkdir -p "$ws"
    # A non-existent record must not trigger stamping — behavior unchanged, so
    # the template's baked placeholder survives (no image build happened here).
    run _scaffold_with_version_file bare "$ws" "$BATS_TEST_TMPDIR/does-not-exist"
    assert_success
    run grep '^DEVCONTAINER_VERSION=' "$ws/.vig-os"
    assert_output "DEVCONTAINER_VERSION={{IMAGE_TAG}}"
}

@test "init-workspace prefers an explicit VIG_OS_VERSION over the VERSION record (#921)" {
    ws="$BATS_TEST_TMPDIR/e2e-921-override-wins"
    mkdir -p "$ws"
    verfile="$BATS_TEST_TMPDIR/VERSION-loser"
    printf '0.5.0-rc3\n' >"$verfile"
    stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    run env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        VERSION_FILE="$verfile" \
        VIG_OS_VERSION="1.2.3" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode bare
    assert_success
    run grep '^DEVCONTAINER_VERSION=' "$ws/.vig-os"
    assert_output "DEVCONTAINER_VERSION=1.2.3"
}

@test "template ships .typos.toml alongside the typos hook (#855)" {
    # The scaffold's .pre-commit-config.yaml runs the typos hook; without the
    # exception config, scaffold-shipped content (version-check.sh's Nd
    # duration syntax, the synced changelog's "unexcepted" policy term) fails
    # every consumer's lint out of the box.
    run test -f "$TEMPLATE_DIR/.typos.toml"
    assert_success
}

# ── 0.4.0-rc4 field-validation fixes (#859) ──────────────────────────────────

@test "scaffolded githooks use env-based bash shebangs (#859)" {
    for hook in pre-commit commit-msg prepare-commit-msg; do
        run head -1 "$TEMPLATE_DIR/.githooks/$hook"
        assert_output "#!/usr/bin/env bash"
    done
}

@test "scaffolded githooks accept the nix dev-shell as sanctioned (#859)" {
    # direnv mode has no container; the guard must not require IN_CONTAINER
    # when the commit happens inside the flake dev-shell (IN_NIX_SHELL).
    for hook in pre-commit commit-msg prepare-commit-msg; do
        run grep -F 'IN_NIX_SHELL' "$TEMPLATE_DIR/.githooks/$hook"
        assert_success
    done
}

@test "scaffolded lifecycle scripts keep the BASH_SOURCE pipe-safety fallback (#859)" {
    # Regression caught by a consumer's own tests: bare ${BASH_SOURCE[0]}
    # dies with "unbound variable" under `set -u` when piped (curl | bash).
    for script in initialize post-create post-attach version-check; do
        # shellcheck disable=SC2016
        run grep -F '${BASH_SOURCE[0]:-$0}' "$TEMPLATE_DIR/.devcontainer/scripts/$script.sh"
        assert_success
        # and no bare form remains
        # shellcheck disable=SC2016
        run grep -F '${BASH_SOURCE[0]}"' "$TEMPLATE_DIR/.devcontainer/scripts/$script.sh"
        assert_failure
    done
}

@test "init-workspace devcontainer-mode prune keeps pre-existing flake.nix and .envrc (#859)" {
    # The prune deleted hyrr's and talys' own nix-direnv setup. Only files the
    # scaffold itself created may be pruned.
    ws=$(mktemp -d)
    printf '# my own flake\n' > "$ws/flake.nix"
    printf 'use flake .#custom\n' > "$ws/.envrc"
    TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" WORKSPACE_DIR="$ws" \
        SHORT_NAME=probe ORG_NAME=Probe GITHUB_REPOSITORY=probe/probe \
        run bash "$INIT_WORKSPACE_SH" --no-prompts --force --mode devcontainer
    assert_success
    run cat "$ws/flake.nix"
    assert_output "# my own flake"
    run cat "$ws/.envrc"
    assert_output "use flake .#custom"
    rm -rf "$ws"
}

@test "init-workspace tolerates a preserved justfile.project without a sync recipe (#859)" {
    # Old-generation consumers (pre-sync recipe) made the installer exit 1
    # after an otherwise complete scaffold (hyrr). Must warn, not fail.
    run grep -n 'just sync' "$INIT_WORKSPACE_SH"
    assert_success
    # the invocation must be non-fatal
    run grep -E 'just sync.*\|\||if.*just.*--show.*sync|just --show sync' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "typos hook passes --force-exclude in repo and template configs (#859)" {
    # prek passes staged filenames explicitly; without --force-exclude, typos
    # ignores [files] extend-exclude and scans binary artifacts (three
    # consumer repos hit garbage findings on PDFs/SVGs/bin fixtures).
    run grep -F 'entry: typos --force-exclude' "$PROJECT_ROOT/.pre-commit-config.yaml"
    assert_success
    run grep -F 'entry: typos --force-exclude' "$TEMPLATE_DIR/.pre-commit-config.yaml"
    assert_success
}

# ── upgrade must deliver the CI-contract base recipes (#877) ──────────────────
# 0.4.0 relocated the base recipes (lint/format/precommit/test/test-cov/sync/
# update) from the retired .devcontainer/justfile.base into justfile.project,
# which is preserved on upgrade — so a 0.3.x consumer never received them while
# the shipped ci.yml calls `just sync` / `just precommit` / `just test` (CI
# failed with "justfile does not contain recipe 'sync'"). The upgrade must
# append whichever contract recipes the preserved file does not resolve, and
# drop the stale .devcontainer/justfile.base.

# Run the real script as an upgrade: real `just` stays on PATH (the repair
# probes recipes via `just --show`), `uv` is stubbed so the trailing
# `just sync` is a fast no-op instead of a real dependency sync.
_upgrade() {
    local mode="$1" ws="$2"
    local stub="$BATS_TEST_TMPDIR/stub-uv"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/uv"
    chmod +x "$stub/uv"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode "$mode"
}

# A pre-0.4.0 consumer justfile.project: team recipes, no base recipes.
_pre040_project_justfile() {
    cat > "$1/justfile.project" <<'EOF'
# SENTINEL-877 pre-0.4.0 consumer recipes (no base recipes)
project := "consumer877"

[group('info')]
info:
    @echo "Project: {{ project }}"
EOF
}

@test "upgrade appends missing CI-contract recipes to a preserved justfile.project (#877)" {
    real_just="$(command -v just)"
    ws="$BATS_TEST_TMPDIR/e2e-877-repair"
    mkdir -p "$ws"
    _pre040_project_justfile "$ws"
    run _upgrade both "$ws"
    assert_success
    # consumer content is preserved, not overwritten
    run grep -q 'SENTINEL-877' "$ws/justfile.project"
    assert_success
    # every CI-contract recipe resolves after the upgrade
    for r in lint format precommit test test-cov sync update; do
        run bash -c "cd '$ws' && '$real_just' --show $r"
        assert_success
    done
}

@test "justfile.project repair keeps customized recipes and is idempotent (#877)" {
    real_just="$(command -v just)"
    ws="$BATS_TEST_TMPDIR/e2e-877-idem"
    mkdir -p "$ws"
    _pre040_project_justfile "$ws"
    cat >> "$ws/justfile.project" <<'EOF'

# consumer-customized test runner
test *args:
    @echo "SENTINEL-877-custom-test"
EOF
    run _upgrade both "$ws"
    assert_success
    run _upgrade both "$ws"
    assert_success
    # still parses (a duplicate append would be a just parse error)...
    run bash -c "cd '$ws' && '$real_just' --list"
    assert_success
    # ...the customized recipe wins over the template one...
    run bash -c "cd '$ws' && '$real_just' --show test"
    assert_output --partial 'SENTINEL-877-custom-test'
    # ...and each appended recipe appears exactly once
    run bash -c "grep -Ec '^sync[ :]' '$ws/justfile.project'"
    assert_output "1"
}

@test "repair skips with a warning when the justfile graph does not parse (#877)" {
    # A syntax error in the preserved justfile.project makes `just --show`
    # fail for EVERY recipe, so the probe would misread all of them as
    # missing and append duplicates on each --force run — turning a fixable
    # parse error into hard "recipe redefined" failures. The repair must
    # detect the broken graph, warn, and skip all appends (non-fatally).
    ws="$BATS_TEST_TMPDIR/e2e-877-broken"
    mkdir -p "$ws"
    cat > "$ws/justfile.project" <<'EOF'
# SENTINEL-877 broken consumer file: defines sync but has a syntax error
sync:
    @echo "SENTINEL-877-consumer-sync"

this line is not valid justfile syntax
EOF
    run _upgrade both "$ws"
    assert_success
    assert_output --partial 'skipping base-recipe repair'
    run _upgrade both "$ws"
    assert_success
    # nothing was appended: sync still defined exactly once, no repair banner
    run bash -c "grep -Ec '^sync[ :]' '$ws/justfile.project'"
    assert_output "1"
    run grep -q 'BASE RECIPES appended' "$ws/justfile.project"
    assert_failure
}

@test "upgrade removes the retired .devcontainer/justfile.base (#877)" {
    ws="$BATS_TEST_TMPDIR/e2e-877-stale"
    mkdir -p "$ws/.devcontainer"
    printf '# retired 0.3.x base recipes\n' >"$ws/.devcontainer/justfile.base"
    run _upgrade both "$ws"
    assert_success
    run test -e "$ws/.devcontainer/justfile.base"
    assert_failure
}

@test "direnv-mode upgrade leaves a pre-existing .devcontainer untouched, incl. justfile.base (#877)" {
    # A consumer-owned .devcontainer/ is never modified in direnv mode (#738);
    # the stale-file cleanup must respect that boundary.
    ws="$BATS_TEST_TMPDIR/e2e-877-direnv"
    mkdir -p "$ws/.devcontainer"
    printf '# consumer-owned devcontainer file\n' >"$ws/.devcontainer/justfile.base"
    run _upgrade direnv "$ws"
    assert_success
    run test -f "$ws/.devcontainer/justfile.base"
    assert_success
}

@test "init-workspace verifies the root justfile scaffold import block (#877)" {
    # One field consumer (talys) ended up with a root justfile carrying no
    # `import?` lines at all, so even present recipes were unreachable. The
    # script must check for the scaffold import block and warn when absent.
    run grep -F "import? 'justfile.project'" "$INIT_WORKSPACE_SH"
    assert_success
}

# ── upgrade must not clobber a customized .pre-commit-config.yaml (#878) ──────
# The scaffold upgrade replaced the consumer's .pre-commit-config.yaml
# wholesale, silently dropping the repo-specific global `exclude:` block and
# per-hook `exclude:` keys (hyrr: the hook suite then "fixed" ~45 physics data
# files it must never touch, and detect-private-key false-flagged a file with
# PEM marker literals). Like justfile.project (#877), the consumer owns the
# file: it is preserved on upgrade, the upgrade prints a diff against the
# template so hook-stack evolution stays visible, and a prek parse gate warns
# when the preserved config would break every commit in the new image.

# A consumer .pre-commit-config.yaml: global + per-hook excludes (hyrr shape).
_custom_precommit_config() {
    cat > "$1/.pre-commit-config.yaml" <<'EOF'
# SENTINEL-878 consumer hook config
exclude: ^data/stopping/|\.dat$
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: cef0300fd0fc4d2a87a85fa2093c6b283ea36f4b  # v5.0.0
    hooks:
      - id: detect-private-key
        exclude: ^worker/src/index\.ts$
EOF
}

@test "upgrade preserves a customized .pre-commit-config.yaml (#878)" {
    ws="$BATS_TEST_TMPDIR/e2e-878-preserve"
    mkdir -p "$ws"
    _custom_precommit_config "$ws"
    run _upgrade both "$ws"
    assert_success
    # the consumer file survives verbatim: global exclude + per-hook exclude
    run grep -q 'SENTINEL-878' "$ws/.pre-commit-config.yaml"
    assert_success
    run grep -q '^exclude: \^data/stopping/' "$ws/.pre-commit-config.yaml"
    assert_success
    run grep -q 'worker/src/index' "$ws/.pre-commit-config.yaml"
    assert_success
}

@test "upgrade prints a template diff hint for a preserved .pre-commit-config.yaml (#878)" {
    ws="$BATS_TEST_TMPDIR/e2e-878-diff"
    mkdir -p "$ws"
    _custom_precommit_config "$ws"
    run _upgrade both "$ws"
    assert_success
    assert_output --partial 'Preserved .pre-commit-config.yaml differs from the template'
    # the hint shows template evolution the preserved file lacks
    assert_output --partial 'default_language_version'
}

@test "no .pre-commit-config.yaml diff hint when it matches the template (#878)" {
    # Fresh scaffold delivers the template file; re-running the upgrade must
    # stay silent (no spurious warning on every upgrade of a stock consumer).
    ws="$BATS_TEST_TMPDIR/e2e-878-stock"
    mkdir -p "$ws"
    run _upgrade both "$ws"
    assert_success
    run _upgrade both "$ws"
    assert_success
    refute_output --partial 'Preserved .pre-commit-config.yaml differs from the template'
}

@test "upgrade warns when the preserved .pre-commit-config.yaml does not validate (#878)" {
    # A preserved config prek cannot load breaks every commit in the new
    # image; the upgrade must warn loudly — and stay non-fatal (#877 parse
    # gate precedent).
    ws="$BATS_TEST_TMPDIR/e2e-878-invalid"
    mkdir -p "$ws"
    cat > "$ws/.pre-commit-config.yaml" <<'EOF'
# SENTINEL-878 broken consumer config
repos: this-is-not-a-repo-list
EOF
    run _upgrade both "$ws"
    assert_success
    assert_output --partial 'does not validate'
    # and the broken file is still preserved, not clobbered
    run grep -q 'SENTINEL-878' "$ws/.pre-commit-config.yaml"
    assert_success
}

# ── upgrade must flag preserved files still invoking `pre-commit` (#881) ──────
# The 0.4.0 image ships `prek` only (#778); a one-cycle `pre-commit` shim
# covers 0.4.x. Preserved consumer files (justfile.project recipes, extra
# .githooks scripts, .pre-commit-config.yaml entries) that still invoke the
# retired binary would otherwise exit 127 at first use — the upgrade must
# scan them and warn with file:line, non-fatally (#877/#878 precedent).

@test "upgrade warns file:line when preserved files still invoke pre-commit (#881)" {
    ws="$BATS_TEST_TMPDIR/e2e-881-hit"
    mkdir -p "$ws/.githooks"
    # vault shape: preserved recipe calls the retired binary
    cat > "$ws/justfile.project" <<'EOF'
# SENTINEL-881 consumer recipes
sync:
    uv sync

precommit:
    uv run pre-commit run --all-files

test:
    @echo test
EOF
    # consumer-owned hook outside the template set survives the rsync
    cat > "$ws/.githooks/pre-push" <<'EOF'
#!/bin/bash
pre-commit run --all-files
EOF
    chmod +x "$ws/.githooks/pre-push"
    run _upgrade both "$ws"
    assert_success
    assert_output --partial "retired 'pre-commit' binary"
    # file:line listing for both surfaces
    assert_output --regexp 'justfile\.project:[0-9]+'
    assert_output --regexp '\.githooks/pre-push:[0-9]+'
    # points at the migration doc and the drop-in runner
    assert_output --partial 'MIGRATION.md'
    assert_output --partial 'prek'
}

@test "no pre-commit-reference warning on a stock scaffold (#881)" {
    ws="$BATS_TEST_TMPDIR/e2e-881-stock"
    mkdir -p "$ws"
    run _upgrade both "$ws"
    assert_success
    refute_output --partial "retired 'pre-commit' binary"
    run _upgrade both "$ws"
    assert_success
    refute_output --partial "retired 'pre-commit' binary"
}

@test "pre-commit scan skips filenames, repo URLs, stage names, prek (#881)" {
    # False-positive guard: none of these are invocations of the retired
    # binary — the config filename, pre-commit-hooks repo URLs, YAML stage
    # names, comments, and the prek runner itself must not trip the warning.
    ws="$BATS_TEST_TMPDIR/e2e-881-clean"
    mkdir -p "$ws"
    cat > "$ws/.pre-commit-config.yaml" <<'EOF'
# SENTINEL-881 clean consumer config: mentions .pre-commit-config.yaml
default_stages: [pre-commit]
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: cef0300fd0fc4d2a87a85fa2093c6b283ea36f4b  # v5.0.0
    hooks:
      - id: end-of-file-fixer
        stages:
          - pre-commit
EOF
    cat > "$ws/justfile.project" <<'EOF'
# SENTINEL-881 clean consumer recipes (see https://pre-commit.com)
sync:
    uv sync

precommit:
    prek run --all-files

test:
    @echo test
EOF
    run _upgrade both "$ws"
    assert_success
    refute_output --partial "retired 'pre-commit' binary"
}

# ── preserved-file diff preview must use git, not diff(1) (#916) ──────────────
# The image ships git but no diff(1)/cmp(1); the #878 preview called `diff`,
# which prints "diff: command not found" and an empty box in-container. Render
# the divergence with `git diff --no-index` (its --quiet form gates the block;
# --no-index exits 1 when files differ, which is the expected signal).

@test "preserved-file diff preview uses git diff --no-index, not diff(1)/cmp(1) (#916)" {
    run grep -nE 'git diff --no-index' "$INIT_WORKSPACE_SH"
    assert_success
    # no bare diff(1) short-flag or cmp(1) invocation survives (both absent from
    # the image); `git diff --no-index` (long flags) is the sanctioned form.
    run grep -nE '(^|[[:space:]])diff -[a-z]|(^|[[:space:]])cmp[[:space:]]' "$INIT_WORKSPACE_SH"
    assert_failure
}

@test "preserved .pre-commit-config.yaml diff preview renders real content, not 'command not found' (#916)" {
    ws="$BATS_TEST_TMPDIR/e2e-916-gitdiff"
    mkdir -p "$ws"
    _custom_precommit_config "$ws"
    run _upgrade both "$ws"
    assert_success
    refute_output --partial 'command not found'
    assert_output --partial 'Preserved .pre-commit-config.yaml differs from the template'
    # a real hunk line from the template the preserved file lacks
    assert_output --partial 'default_language_version'
}

# ── upgrade must preserve a customized .typos.toml, no dual configs (#913) ────
# The typos hook reads a project's spell-check exceptions; a consumer curates
# repo-specific extend-words/extend-exclude that a template overwrite silently
# destroyed (their lint then flags legitimate domain terms). Preserve it like
# .pre-commit-config.yaml (#878) and print the template diff. The `typos` tool
# also reads the legacy `_typos.toml`, so a consumer carrying that must NOT also
# receive the template `.typos.toml` — two active configs would collide.

@test ".typos.toml is preserved on --force upgrade (#913)" {
    # shellcheck disable=SC2016
    run grep -E '"\.typos\.toml"' "$INIT_WORKSPACE_SH"
    assert_success
}

@test "upgrade preserves a customized .typos.toml (#913)" {
    ws="$BATS_TEST_TMPDIR/e2e-913-preserve"
    mkdir -p "$ws"
    printf '# SENTINEL-913 consumer typos config\n[default.extend-words]\nfoo = "foo"\n' \
        >"$ws/.typos.toml"
    run _upgrade both "$ws"
    assert_success
    run grep -q 'SENTINEL-913' "$ws/.typos.toml"
    assert_success
}

@test "upgrade prints a template diff hint for a preserved .typos.toml (#913)" {
    ws="$BATS_TEST_TMPDIR/e2e-913-diff"
    mkdir -p "$ws"
    # a config lacking the template's exception words
    printf '# SENTINEL-913 minimal consumer typos config\n' >"$ws/.typos.toml"
    run _upgrade both "$ws"
    assert_success
    refute_output --partial 'command not found'
    assert_output --partial 'Preserved .typos.toml differs from the template'
    # a template exception word the preserved file lacks shows in the diff
    assert_output --partial 'unexcepted'
}

@test "upgrade with a legacy _typos.toml does not leave dual typos configs (#913)" {
    # vault scenario: consumer carries _typos.toml and no .typos.toml. Shipping
    # the template .typos.toml alongside it would give two active configs.
    ws="$BATS_TEST_TMPDIR/e2e-913-legacy"
    mkdir -p "$ws"
    printf '# SENTINEL-913 legacy typos config\n[default.extend-words]\nmyterm = "myterm"\n' \
        >"$ws/_typos.toml"
    run _upgrade both "$ws"
    assert_success
    # legacy config preserved verbatim
    run grep -q 'SENTINEL-913' "$ws/_typos.toml"
    assert_success
    # template .typos.toml NOT shipped -> single active config
    run test -e "$ws/.typos.toml"
    assert_failure
}

# ── pre-commit reference scan must cover preserved workflows (#916) ────────────
# The #881 scan only looked at justfile.project and .githooks/, but a consumer
# CI workflow that still invokes the retired `pre-commit` binary breaks the same
# way. Extend the scan to preserved .github/workflows/*.yml. A YAML `name:` step
# description or a comment mention must NOT be flagged; only real invocations.

@test "pre-commit scan flags a real invocation in a consumer workflow (#916)" {
    ws="$BATS_TEST_TMPDIR/e2e-916-workflow-hit"
    mkdir -p "$ws/.github/workflows"
    # consumer-owned workflow (not in the template set) survives the rsync
    cat > "$ws/.github/workflows/consumer-ci.yml" <<'EOF'
name: Consumer CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      # pre-commit MENTIONONLY: migrate to prek before 0.5
      - name: Run pre-commit hooks
        run: uv run pre-commit run --all-files
EOF
    run _upgrade both "$ws"
    assert_success
    assert_output --partial "retired 'pre-commit' binary"
    # the real invocation line is flagged with file:line
    assert_output --regexp '\.github/workflows/consumer-ci\.yml:[0-9]+'
    # neither the comment mention nor the step `name:` description is flagged
    refute_output --partial 'MENTIONONLY'
    refute_output --partial 'Run pre-commit hooks'
}

@test "no pre-commit warning for a workflow that only mentions it (#916)" {
    ws="$BATS_TEST_TMPDIR/e2e-916-workflow-clean"
    mkdir -p "$ws/.github/workflows"
    cat > "$ws/.github/workflows/consumer-clean.yml" <<'EOF'
name: Consumer CI
on: [push]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      # pre-commit was replaced by prek
      - name: Run pre-commit hooks
        run: uv run prek run --all-files
EOF
    run _upgrade both "$ws"
    assert_success
    refute_output --partial "retired 'pre-commit' binary"
}

# ── origin must resolve before any filesystem mutation (#916) ─────────────────
# Under --no-prompts, the GITHUB_REPOSITORY resolution ran AFTER the rsync copy,
# so an abort left a half-scaffolded tree behind. Resolve (and validate) the
# origin BEFORE the first filesystem mutation so a failure leaves the workspace
# untouched.

@test "no-prompts without a derivable origin aborts before mutating the workspace (#916)" {
    ws="$BATS_TEST_TMPDIR/e2e-916-no-origin"
    mkdir -p "$ws"
    # no .git origin and GITHUB_REPOSITORY unset (cleared: CI may export it)
    run env -u GITHUB_REPOSITORY \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=probe \
        bash "$INIT_WORKSPACE_SH" --no-prompts --mode both
    assert_failure
    assert_output --partial 'GITHUB_REPOSITORY is required'
    # the workspace was never scaffolded: still empty (no template files copied)
    run bash -c "ls -A '$ws'"
    assert_output ""
}

# ── --preview: report-only upgrade preview (#886) ─────────────────────────────
# `--preview` runs the existing conflict-report machinery (OVERWRITTEN /
# PRESERVED), extended with the mode-prune DELETED listing and the ADDED
# listing, then exits 0 before mutating anything. install.sh forwards it; a
# preview is by definition of an upgrade, so it must ride the --force report
# path without requiring --force.

# Run the real script in preview mode against workspace $1 (extra args pass
# through, e.g. --mode). `uv` is stubbed like _upgrade for consistency; a
# correct preview never reaches the `just sync` step anyway.
_preview() {
    local ws="$1"
    shift
    local stub="$BATS_TEST_TMPDIR/stub-uv-886"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/uv"
    chmod +x "$stub/uv"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --preview --no-prompts "$@"
}

@test "init-workspace --preview exits 0 and prints the file report (#886)" {
    ws="$BATS_TEST_TMPDIR/e2e-886-report"
    mkdir -p "$ws"
    _upgrade both "$ws"
    run _preview "$ws" --mode both
    assert_success
    assert_output --partial "OVERWRITTEN"
    assert_output --partial "PRESERVED"
    assert_output --partial "Preview complete"
}

@test "init-workspace --preview leaves the tree byte-identical (#886)" {
    ws="$BATS_TEST_TMPDIR/e2e-886-intact"
    mkdir -p "$ws"
    _upgrade both "$ws"
    cp -a "$ws" "$ws.before"
    run _preview "$ws" --mode both
    assert_success
    run diff -r "$ws" "$ws.before"
    assert_success
}

@test "init-workspace --preview lists prune deletions without deleting (#886)" {
    # The retired .devcontainer/justfile.base is removed on a real upgrade
    # (#877); the preview must list it as DELETED and leave it in place.
    ws="$BATS_TEST_TMPDIR/e2e-886-deletions"
    mkdir -p "$ws/.devcontainer"
    printf '# retired 0.3.x base recipes\n' >"$ws/.devcontainer/justfile.base"
    run _preview "$ws" --mode both
    assert_success
    assert_output --partial "DELETED"
    assert_output --partial ".devcontainer/justfile.base"
    run test -f "$ws/.devcontainer/justfile.base"
    assert_success
}

@test "init-workspace --preview lists the direnv-mode .devcontainer prune (#886)" {
    # direnv mode prunes a .devcontainer/ that did not pre-exist with content
    # (#738); the preview must list the removal and leave the dir in place.
    ws="$BATS_TEST_TMPDIR/e2e-886-direnv-prune"
    mkdir -p "$ws/.devcontainer"
    run _preview "$ws" --mode direnv
    assert_success
    assert_output --partial "DELETED"
    assert_output --partial ".devcontainer/"
    run test -d "$ws/.devcontainer"
    assert_success
}

@test "init-workspace --preview works without --force on a populated tree (#886)" {
    # install.sh forwards --preview on its own; the preview must not trip the
    # "Workspace is not empty" refusal nor require an explicit --force.
    ws="$BATS_TEST_TMPDIR/e2e-886-no-force"
    mkdir -p "$ws"
    _upgrade both "$ws"
    run _preview "$ws" --mode both
    assert_success
    refute_output --partial "Workspace is not empty"
}

@test "init-workspace --preview lists template files new to the tree as ADDED (#886)" {
    ws="$BATS_TEST_TMPDIR/e2e-886-added"
    mkdir -p "$ws"
    _upgrade both "$ws"
    rm "$ws/justfile"
    run _preview "$ws" --mode both
    assert_success
    assert_output --partial "ADDED"
    assert_output --partial "justfile"
    # ...and the preview did not scaffold it back
    run test -e "$ws/justfile"
    assert_failure
}

# ── .vig-os project manifest (#885) ───────────────────────────────────────────
# .vig-os is the project's declarative manifest: the delivery mode and the
# project identity (short name, org, GitHub repo) are persisted on every
# (re)scaffold and read back before prompting — precedence flag/env > .vig-os >
# prompt/default — so a manifest-bearing repo upgrades with `--force` and no
# mode/identity flags while keeping its shape and names. `DEVKIT_MODULES` is
# reserved for the capability-module declaration (#884) and survives upgrades.

# Re-run the real script as an upgrade with NO mode/identity flags or env:
# everything must resolve from the workspace's own .vig-os manifest.
_upgrade_no_flags() {
    local ws="$1"
    local stub="$BATS_TEST_TMPDIR/stub-bin-885"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts
}

@test "template .vig-os carries the manifest key set (#885)" {
    for key in DEVCONTAINER_VERSION DEVKIT_MODE DEVKIT_PROJECT DEVKIT_ORG \
        DEVKIT_REPO DEVKIT_MODULES; do
        run grep -E "^${key}=" "$TEMPLATE_DIR/.vig-os"
        assert_success
    done
}

@test "template .vig-os ships no baked-in delivery mode (#885)" {
    # The template value lands verbatim in the consumer's .vig-os between the
    # rsync overwrite and the resolved write-back. A non-empty DEVKIT_MODE in
    # that window is a mode nobody chose: an abort inside it would persist the
    # template's mode and legitimize a reshape on the next run. Empty is
    # treated as unset by every parser, so ship it empty.
    run grep -x 'DEVKIT_MODE=' "$TEMPLATE_DIR/.vig-os"
    assert_success
}

@test "fresh scaffold persists resolved mode and identity in .vig-os (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-writeback"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run grep -x 'DEVKIT_MODE=direnv' "$ws/.vig-os"
    assert_success
    run grep -x 'DEVKIT_PROJECT=testproj' "$ws/.vig-os"
    assert_success
    # _scaffold sets no ORG_NAME, so the --no-prompts default is persisted
    run grep -x 'DEVKIT_ORG=vigOS/devc' "$ws/.vig-os"
    assert_success
    run grep -x 'DEVKIT_REPO=test/repo' "$ws/.vig-os"
    assert_success
}

@test "manifest-bearing upgrade keeps devcontainer shape and names, no flags (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-up-devc"
    mkdir -p "$ws"
    run _scaffold devcontainer "$ws"
    assert_success
    run _upgrade_no_flags "$ws"
    assert_success
    assert_output --partial "from .vig-os manifest"
    run test -d "$ws/.devcontainer"
    assert_success
    run test -e "$ws/flake.nix"
    assert_failure
    run test -e "$ws/.envrc"
    assert_failure
    run test -f "$ws/justfile.project"
    assert_success
    run grep -x 'DEVKIT_MODE=devcontainer' "$ws/.vig-os"
    assert_success
}

@test "manifest-bearing upgrade keeps direnv shape and names, no flags (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-up-direnv"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run _upgrade_no_flags "$ws"
    assert_success
    assert_output --partial "from .vig-os manifest"
    run test -e "$ws/.devcontainer"
    assert_failure
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/justfile.project"
    assert_success
    run grep -x 'DEVKIT_MODE=direnv' "$ws/.vig-os"
    assert_success
    run grep -x 'DEVKIT_PROJECT=testproj' "$ws/.vig-os"
    assert_success
}

@test "manifest-bearing upgrade keeps both shape and names, no flags (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-up-both"
    mkdir -p "$ws"
    run _scaffold both "$ws"
    assert_success
    run _upgrade_no_flags "$ws"
    assert_success
    run test -d "$ws/.devcontainer"
    assert_success
    run test -f "$ws/flake.nix"
    assert_success
    run test -f "$ws/justfile.project"
    assert_success
    run grep -x 'DEVKIT_MODE=both' "$ws/.vig-os"
    assert_success
}

@test "persisted-mode vs requested-mode mismatch refuses, pointing at --preview (#885)" {
    # Mode switching is destructive (e.g. both -> bare deletes .devcontainer/)
    # and out of scope here: it must never happen implicitly. A --mode that
    # contradicts the persisted DEVKIT_MODE refuses instead of reshaping.
    ws="$BATS_TEST_TMPDIR/e2e-885-mismatch"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    stub="$BATS_TEST_TMPDIR/stub-bin-885"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    run env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts --mode both
    assert_failure
    assert_output --partial "DEVKIT_MODE"
    assert_output --partial "--preview"
    # the tree was not reshaped
    run test -e "$ws/.devcontainer"
    assert_failure
}

@test "--preview is exempt from the mode-mismatch refusal (#885)" {
    # Preview is report-only, so it is exactly how a user inspects a would-be
    # mode switch before deciding.
    ws="$BATS_TEST_TMPDIR/e2e-885-mismatch-preview"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run _preview "$ws" --mode both
    assert_success
    assert_output --partial "Preview complete"
    run test -e "$ws/.devcontainer"
    assert_failure
}

@test "matching --mode proceeds against a persisted DEVKIT_MODE (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-match"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run _scaffold direnv "$ws"
    assert_success
    run test -e "$ws/.devcontainer"
    assert_failure
}

@test "upgrade preserves a persisted DEVKIT_MODULES value (#885)" {
    # Reserved key (#884): .vig-os is a managed file, so the consumer's module
    # declaration must be read before the template overwrite and written back.
    ws="$BATS_TEST_TMPDIR/e2e-885-modules"
    mkdir -p "$ws"
    run _scaffold both "$ws"
    assert_success
    sed -i 's/^DEVKIT_MODULES=.*/DEVKIT_MODULES="native rust"/' "$ws/.vig-os"
    run _upgrade_no_flags "$ws"
    assert_success
    run grep -x 'DEVKIT_MODULES="native rust"' "$ws/.vig-os"
    assert_success
}

# ── legacy mode inference (#885) ──────────────────────────────────────────────
# Consumers scaffolded before the manifest carry a version-only .vig-os (or
# none): an upgrade without --mode must infer the delivery mode from the tree
# shape — conservatively (the wider mode on ambiguity), transparently (the
# inference is printed), and without ever reshaping the repo. The inferred
# mode is persisted so the file self-documents from the first upgrade on.

# Strip the workspace manifest back to the pre-#885 version-only form.
_make_legacy_manifest() {
    printf '# vig-os devcontainer configuration\nDEVCONTAINER_VERSION=0.3.9\n' \
        > "$1/.vig-os"
}

# Upgrade with identity env but NO --mode: the legacy path under test.
_upgrade_legacy() {
    local ws="$1"
    local stub="$BATS_TEST_TMPDIR/stub-bin-885L"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts
}

@test "legacy upgrade infers devcontainer mode from a .devcontainer-only tree (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-infer-devc"
    mkdir -p "$ws"
    run _scaffold devcontainer "$ws"
    assert_success
    _make_legacy_manifest "$ws"
    run _upgrade_legacy "$ws"
    assert_success
    assert_output --partial "Inferred delivery mode 'devcontainer'"
    run test -d "$ws/.devcontainer"
    assert_success
    # no reshape: the flake stub must NOT be added to a devcontainer-only repo
    run test -e "$ws/flake.nix"
    assert_failure
    run grep -x 'DEVKIT_MODE=devcontainer' "$ws/.vig-os"
    assert_success
}

@test "legacy upgrade infers direnv mode from a flake/envrc-only tree (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-infer-direnv"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    _make_legacy_manifest "$ws"
    run _upgrade_legacy "$ws"
    assert_success
    assert_output --partial "Inferred delivery mode 'direnv'"
    run test -e "$ws/.devcontainer"
    assert_failure
    run test -f "$ws/flake.nix"
    assert_success
    run grep -x 'DEVKIT_MODE=direnv' "$ws/.vig-os"
    assert_success
}

@test "legacy upgrade infers both from .devcontainer plus the scaffold flake stub (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-infer-both"
    mkdir -p "$ws"
    run _scaffold both "$ws"
    assert_success
    _make_legacy_manifest "$ws"
    run _upgrade_legacy "$ws"
    assert_success
    assert_output --partial "Inferred delivery mode 'both'"
    run test -d "$ws/.devcontainer"
    assert_success
    run test -f "$ws/flake.nix"
    assert_success
    run grep -x 'DEVKIT_MODE=both' "$ws/.vig-os"
    assert_success
}

@test "ambiguous legacy tree (consumer flake + .devcontainer) widens to both (#885)" {
    # The #859 combination: a devcontainer-mode repo whose owners added their
    # own nix-direnv setup. Resolve to the WIDER mode, print the inference,
    # and keep the consumer files bit-identical (they are PRESERVE_FILES).
    ws="$BATS_TEST_TMPDIR/e2e-885-infer-ambiguous"
    mkdir -p "$ws"
    run _scaffold devcontainer "$ws"
    assert_success
    _make_legacy_manifest "$ws"
    printf '# SENTINEL-885 my own flake\n' > "$ws/flake.nix"
    printf 'use flake .#custom\n' > "$ws/.envrc"
    run _upgrade_legacy "$ws"
    assert_success
    assert_output --partial "Inferred delivery mode 'both'"
    run test -d "$ws/.devcontainer"
    assert_success
    run cat "$ws/flake.nix"
    assert_output "# SENTINEL-885 my own flake"
    run cat "$ws/.envrc"
    assert_output "use flake .#custom"
    run grep -x 'DEVKIT_MODE=both' "$ws/.vig-os"
    assert_success
}

@test "aborted legacy upgrade does not poison DEVKIT_MODE for the next run (#885)" {
    # Torn-state window: the template rsync overwrites .vig-os before the
    # resolved values are written back, and resolve_github_repository sits
    # inside that window — under --no-prompts it exits 1 on a legacy tree
    # whose origin is not github.com. The abort must leave no mode the repo
    # never chose, or the NEXT --force run trusts the persisted value and
    # silently re-adds .devcontainer/ to a direnv-shaped repo.
    ws="$BATS_TEST_TMPDIR/e2e-885-torn"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    _make_legacy_manifest "$ws"
    git init -q "$ws"
    git -C "$ws" remote add origin https://gitlab.example.com/acme/legacy.git

    # First run: no GITHUB_REPOSITORY env, non-github origin -> aborts after
    # the template overwrite, before the late write-back.
    stub="$BATS_TEST_TMPDIR/stub-bin-885T"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    # `env -u GITHUB_REPOSITORY`: GitHub Actions exports the variable
    # globally, which would satisfy the resolver in CI and mask the abort.
    run env -u GITHUB_REPOSITORY PATH="$stub:$PATH" \
        TEMPLATE_DIR="$PROJECT_ROOT/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        bash "$INIT_WORKSPACE_SH" --force --no-prompts
    assert_failure
    assert_output --partial "GITHUB_REPOSITORY"

    # The torn manifest must not claim the template's mode...
    run grep -x 'DEVKIT_MODE=both' "$ws/.vig-os"
    assert_failure
    # ...and the mode resolved BEFORE the abort is already persisted (early
    # write-back), so the manifest never lies even mid-run.
    run grep -x 'DEVKIT_MODE=direnv' "$ws/.vig-os"
    assert_success

    # The second (repaired) run keeps the direnv shape instead of silently
    # re-adding .devcontainer/.
    run _upgrade_legacy "$ws"
    assert_success
    run test -e "$ws/.devcontainer"
    assert_failure
    run grep -x 'DEVKIT_MODE=direnv' "$ws/.vig-os"
    assert_success
}

# ── bare delivery mode (#885) ─────────────────────────────────────────────────
# `bare` ships the standards layer only — justfiles, hooks config, .github CI,
# .vig-os — and prunes every container/flake artifact
# (.devcontainer/, flake.nix, .envrc) with the same #738/#859 pre-existence
# guards as the other modes. The shipped ci.yml is replaced by a host-native
# variant: no resolve-image, no container jobs — the runner sets up uv
# directly and drives the same `just sync|precommit|test` contract.

@test "init-workspace --mode=bare scaffolds the standards layer only (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-bare"
    mkdir -p "$ws"
    run _scaffold bare "$ws"
    assert_success
    # pruned: container and flake machinery
    run test -e "$ws/.devcontainer"
    assert_failure
    run test -e "$ws/flake.nix"
    assert_failure
    run test -e "$ws/.envrc"
    assert_failure
    # shipped: the standards layer
    for f in justfile justfile.project justfile.local .pre-commit-config.yaml \
        .github/workflows/ci.yml .vig-os; do
        run test -e "$ws/$f"
        assert_success
    done
    run grep -x 'DEVKIT_MODE=bare' "$ws/.vig-os"
    assert_success
}

@test "fresh bare workspace resolves the CI-contract recipes (#885)" {
    # The shipped host-native ci.yml calls `just sync|precommit|test`; the
    # root justfile's .devcontainer imports are optional (import?), so the
    # graph must load and every contract recipe must resolve without any
    # .devcontainer/ recipe file.
    real_just="$(command -v just)"
    ws="$BATS_TEST_TMPDIR/e2e-bare-just"
    mkdir -p "$ws"
    run _scaffold bare "$ws"
    assert_success
    run bash -c "cd '$ws' && '$real_just' --list"
    assert_success
    for r in sync precommit test; do
        run bash -c "cd '$ws' && '$real_just' --show $r"
        assert_success
    done
}

@test "bare-mode ci.yml is host-native: no image resolution, no container jobs (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-bare-ci"
    mkdir -p "$ws"
    run _scaffold bare "$ws"
    assert_success
    run grep -E 'resolve-image|container:' "$ws/.github/workflows/ci.yml"
    assert_failure
    run grep -q 'astral-sh/setup-uv' "$ws/.github/workflows/ci.yml"
    assert_success
    # scorecard-conform: every action reference is SHA-pinned
    run bash -c "grep 'uses:' '$ws/.github/workflows/ci.yml' | grep -vE '@[0-9a-f]{40}'"
    assert_failure
}

@test "bare scaffold preserves a pre-existing .devcontainer/, flake.nix and .envrc (#885)" {
    # Same guards as #738/#859: bare never deletes consumer-owned machinery,
    # even though a stock bare workspace ships none.
    ws="$BATS_TEST_TMPDIR/e2e-bare-guards"
    mkdir -p "$ws/.devcontainer"
    printf '# SENTINEL-885 consumer compose\n' > "$ws/.devcontainer/docker-compose.yml"
    printf '# SENTINEL-885 my own flake\n' > "$ws/flake.nix"
    printf 'use flake .#custom\n' > "$ws/.envrc"
    run _scaffold bare "$ws"
    assert_success
    run grep -q 'SENTINEL-885 consumer compose' "$ws/.devcontainer/docker-compose.yml"
    assert_success
    run cat "$ws/flake.nix"
    assert_output "# SENTINEL-885 my own flake"
    run cat "$ws/.envrc"
    assert_output "use flake .#custom"
}

@test "manifest-bearing upgrade keeps bare shape and names, no flags (#885)" {
    ws="$BATS_TEST_TMPDIR/e2e-885-up-bare"
    mkdir -p "$ws"
    run _scaffold bare "$ws"
    assert_success
    run _upgrade_no_flags "$ws"
    assert_success
    assert_output --partial "from .vig-os manifest"
    run test -e "$ws/.devcontainer"
    assert_failure
    run test -e "$ws/flake.nix"
    assert_failure
    run test -f "$ws/justfile.project"
    assert_success
    run grep -x 'DEVKIT_MODE=bare' "$ws/.vig-os"
    assert_success
    run grep -E 'resolve-image|container:' "$ws/.github/workflows/ci.yml"
    assert_failure
}

@test "preview lists a pre-existing .devcontainer/ as preserved in direnv/bare modes (#885)" {
    # A populated consumer .devcontainer/ is kept by the #738 guard but was
    # silently absent from the preview report — the mode-switch UX needs the
    # explicit "preserved" line.
    ws="$BATS_TEST_TMPDIR/e2e-885-preview-preserved"
    mkdir -p "$ws/.devcontainer"
    printf '# consumer-owned\n' > "$ws/.devcontainer/docker-compose.yml"
    run _preview "$ws" --mode direnv
    assert_success
    assert_output --partial ".devcontainer/ (pre-existing"
}

# ── direnv nix-direct CI lane (#854) ──────────────────────────────────────────
# `direnv` ships the flake + .envrc but no .devcontainer/, so its CI cannot run
# in the container. init-workspace overlays a nix-direct ci.yml variant (like the
# bare overlay): no resolve-image, no container jobs — the runner installs Nix
# and drives `nix develop -c just sync|precommit|test`.

@test "direnv-mode ci.yml is nix-direct: no image resolution, no container jobs (#854)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv-ci"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    # no container/resolve-image machinery (ignore explanatory comment lines)
    run bash -c "grep -vE '^[[:space:]]*#' '$ws/.github/workflows/ci.yml' | grep -E 'resolve-image|container:'"
    assert_failure
    # nix-direct: install-nix + nix develop drive the just contract
    run grep -q 'cachix/install-nix-action' "$ws/.github/workflows/ci.yml"
    assert_success
    run grep -q 'nix develop -c just' "$ws/.github/workflows/ci.yml"
    assert_success
    # scorecard-conform: every action reference is SHA-pinned
    run bash -c "grep 'uses:' '$ws/.github/workflows/ci.yml' | grep -vE '@[0-9a-f]{40}'"
    assert_failure
}

@test "direnv-mode ci.yml drops the container-only env (#854)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv-ci-env"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run bash -c "grep -vE '^[[:space:]]*#' '$ws/.github/workflows/ci.yml' | grep -E 'PREK_HOME|UV_PROJECT_ENVIRONMENT'"
    assert_failure
}

@test "direnv-mode ci.yml wires the prek version-skew guard (#854)" {
    ws="$BATS_TEST_TMPDIR/e2e-direnv-ci-guard"
    mkdir -p "$ws"
    run _scaffold direnv "$ws"
    assert_success
    run grep -q 'command -v prek' "$ws/.github/workflows/ci.yml"
    assert_success
}

@test "prepare-release.yml uses the shared resolve-image action, no latest fallback (#854)" {
    wf="$TEMPLATE_DIR/.github/workflows/prepare-release.yml"
    run grep -q 'uses: ./.github/actions/resolve-image' "$wf"
    assert_success
    # the forked inline awk resolver + silent `latest` fallback is gone
    run grep -q 'TAG="latest"' "$wf"
    assert_failure
}

@test "container-mode ci.yml wires the prek version-skew guard (#854)" {
    # The devcontainer-mode lint job must fail fast with an actionable message
    # when the pinned image predates prek, rather than an opaque exit 127.
    ws="$BATS_TEST_TMPDIR/e2e-container-guard"
    mkdir -p "$ws"
    run _scaffold devcontainer "$ws"
    assert_success
    run grep -q 'command -v prek' "$ws/.github/workflows/ci.yml"
    assert_success
}

@test "direnv overlay leaves devcontainer + bare + both modes container-based (#854)" {
    # The overlay is direnv-only: the other modes keep the container ci.yml
    # (devcontainer/both) or the bare host-native one.
    for mode in devcontainer both; do
        ws="$BATS_TEST_TMPDIR/e2e-direnv-neg-$mode"
        mkdir -p "$ws"
        run _scaffold "$mode" "$ws"
        assert_success
        run grep -q 'resolve-image' "$ws/.github/workflows/ci.yml"
        assert_success
        run grep -q 'nix develop -c just' "$ws/.github/workflows/ci.yml"
        assert_failure
    done
}
