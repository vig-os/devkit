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
