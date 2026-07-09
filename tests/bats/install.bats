#!/usr/bin/env bats
# BATS tests for install.sh
#
# These tests exercise install.sh flags and argument parsing without requiring
# a container runtime.  They complement the pytest-based unit tests in
# tests/test_utils.py::TestInstallScriptUnit.
#
# Test categories:
# - help flag (-h, --help)
# - option documentation
# - unknown option handling
# - dry-run mode
# - version flag
# - force flag
# - organization name flag
# - project name sanitization
# - invalid path handling
# - os detection
# - runtime detection
# - git repository setup
# - upgrade preflight guard (#886)

setup() {
    load test_helper
    INSTALL_SH="$PROJECT_ROOT/install.sh"
}

# ── help ──────────────────────────────────────────────────────────────────────

@test "help flag (-h) exits 0 and prints usage" {
    run bash "$INSTALL_SH" -h
    assert_success
    assert_output --partial "USAGE:"
    assert_output --partial "OPTIONS:"
}

@test "help flag (--help) exits 0 and prints usage" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "vigOS Devcontainer Install Script"
}

@test "help lists all documented options" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "--force"
    assert_output --partial "--version"
    assert_output --partial "--docker"
    assert_output --partial "--podman"
    assert_output --partial "--name"
    assert_output --partial "--org"
    assert_output --partial "--repo"
    assert_output --partial "--dry-run"
    assert_output --partial "--smoke-test"
}

# ── unknown option ────────────────────────────────────────────────────────────

@test "unknown option exits 1 with error" {
    run bash "$INSTALL_SH" --nonexistent
    assert_failure
    assert_output --partial "error"
    assert_output --partial "Unknown option"
}

# ── dry-run ───────────────────────────────────────────────────────────────────

@test "dry-run shows the command that would be executed" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "Would execute:"
    assert_output --partial "init-workspace.sh"
}

@test "dry-run command is derived from the CMD array via printf %q" {
    # The shown command must be rendered from the real CMD array, not a
    # hand-maintained duplicate string (#759).
    # shellcheck disable=SC2016
    run grep "printf '%q" "$INSTALL_SH"
    assert_success
}

@test "dry-run includes image registry in command" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer"
}

@test "dry-run output is shell-quoted for safe copy-paste" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    # The command is rendered from the real CMD array via printf '%q', so each
    # argument is shell-safe (quoted only when it contains special characters).
    assert_output --regexp '[^ ]+:/workspace'
    assert_output --regexp 'ghcr\.io/vig-os/devcontainer:[^ ]+'
}

# ── version flag ──────────────────────────────────────────────────────────────

@test "version flag appears in dry-run command" {
    run bash "$INSTALL_SH" --dry-run --version 1.2.3 .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer:1.2.3"
}

@test "default version is latest" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial "ghcr.io/vig-os/devcontainer:latest"
}

# ── force flag ────────────────────────────────────────────────────────────────

@test "force flag is forwarded to init-workspace.sh" {
    # Clean feature-branch fixture: the upgrade preflight guard (#886) would
    # refuse `.` on a CI checkout (detached HEAD) or a dirty dev tree.
    repo="$BATS_TEST_TMPDIR/force-forward"
    _make_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force "$repo"
    assert_success
    assert_output --partial "--force"
}

@test "smoke-test flag is forwarded to init-workspace.sh" {
    run bash "$INSTALL_SH" --dry-run --smoke-test .
    assert_success
    assert_output --partial "--smoke-test"
}

# ── org flag ──────────────────────────────────────────────────────────────────

@test "default org is vigOS" {
    run bash "$INSTALL_SH" --dry-run .
    assert_success
    assert_output --partial 'ORG_NAME=vigOS'
}

@test "default GITHUB_REPOSITORY is OWNER/REPO when no git origin" {
    local test_dir
    test_dir="$(mktemp -d)"
    run bash "$INSTALL_SH" --dry-run "$test_dir"
    assert_success
    assert_output --partial 'GITHUB_REPOSITORY=OWNER/REPO'
    rm -rf "$test_dir"
}

@test "custom --repo is passed to container" {
    run bash "$INSTALL_SH" --dry-run --repo vig-os/myapp .
    assert_success
    assert_output --partial 'GITHUB_REPOSITORY=vig-os/myapp'
}

@test "custom org is passed to container" {
    run bash "$INSTALL_SH" --dry-run --org MyOrg .
    assert_success
    assert_output --partial 'ORG_NAME=MyOrg'
}

# ── name flag / sanitization ─────────────────────────────────────────────────

@test "project name is sanitized in dry-run" {
    local test_dir
    test_dir="$(mktemp -d)"
    mkdir -p "$test_dir/My-Awesome-Project"

    run bash "$INSTALL_SH" --dry-run "$test_dir/My-Awesome-Project"
    assert_success
    assert_output --partial 'SHORT_NAME=my_awesome_project'

    rm -rf "$test_dir"
}

@test "custom name overrides directory name" {
    run bash "$INSTALL_SH" --dry-run --name custom_name .
    assert_success
    assert_output --partial 'SHORT_NAME=custom_name'
}

# ── invalid path ──────────────────────────────────────────────────────────────

@test "non-existent path exits 1" {
    run bash "$INSTALL_SH" --dry-run /tmp/nonexistent-path-$$
    assert_failure
    assert_output --partial "Directory does not exist"
}

# ── runtime detection ─────────────────────────────────────────────────────────

@test "install.sh includes detect_runtime function" {
    run grep 'detect_runtime()' "$INSTALL_SH"
    assert_success
}

@test "install.sh prefers podman over docker" {
    run grep 'command -v podman' "$INSTALL_SH"
    assert_success
}

@test "install.sh falls back to docker if podman unavailable" {
    run grep 'command -v docker' "$INSTALL_SH"
    assert_success
}

# ── os detection ──────────────────────────────────────────────────────────────

@test "install.sh includes detect_os function" {
    run grep 'detect_os()' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects macOS" {
    run grep 'Darwin\*' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Debian/Ubuntu" {
    run grep 'ubuntu|debian|pop|linuxmint' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Fedora/RHEL" {
    run grep 'fedora|rhel|centos|rocky|almalinux' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects Arch Linux" {
    run grep 'arch|manjaro|endeavouros' "$INSTALL_SH"
    assert_success
}

@test "install.sh detects openSUSE" {
    run grep 'opensuse\*|sles' "$INSTALL_SH"
    assert_success
}

# ── color output ──────────────────────────────────────────────────────────────

@test "install.sh uses colored output for interactive terminal" {
    run grep 'RED=' "$INSTALL_SH"
    assert_success
}

@test "install.sh disables colors for non-interactive terminal" {
    run grep 'if \[ -t 1 \]' "$INSTALL_SH"
    assert_success
}

# ── output functions ──────────────────────────────────────────────────────────

@test "install.sh defines err function for error messages" {
    run grep 'err() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines info function for info messages" {
    run grep 'info() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines warn function for warnings" {
    run grep 'warn() {' "$INSTALL_SH"
    assert_success
}

@test "install.sh defines success function for success messages" {
    run grep 'success() {' "$INSTALL_SH"
    assert_success
}

# ── git repository setup (embedded in install.sh) ────────────────────────────

@test "install.sh includes setup_git_repo function" {
    run grep 'setup_git_repo()' "$INSTALL_SH"
    assert_success
}

@test "install.sh initializes git repo if missing" {
    run grep 'git init -b main' "$INSTALL_SH"
    assert_success
}

@test "install.sh creates initial commit if needed" {
    run grep 'git commit' "$INSTALL_SH"
    assert_success
}

@test "install.sh guards the scaffold commit against a populated directory" {
    # The automatic 'initial project scaffold' commit must only run for a
    # freshly scaffolded (empty) target, gated by the TARGET_WAS_EMPTY flag,
    # so it never sweeps a pre-populated directory into a misleading commit (#759).
    # shellcheck disable=SC2016
    run grep 'TARGET_WAS_EMPTY' "$INSTALL_SH"
    assert_success
}

@test "install.sh verifies main branch exists" {
    run grep 'git rev-parse --verify main' "$INSTALL_SH"
    assert_success
}

@test "install.sh verifies dev branch exists" {
    run grep 'git rev-parse --verify dev' "$INSTALL_SH"
    assert_success
}

@test "install.sh creates dev branch if missing" {
    run grep 'git branch dev' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows remote origin hint" {
    run grep 'git remote add origin' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows push hint" {
    run grep 'git push -u origin main dev' "$INSTALL_SH"
    assert_success
}

# ── user configuration ────────────────────────────────────────────────────────

@test "install.sh includes run_user_conf function" {
    run grep 'run_user_conf()' "$INSTALL_SH"
    assert_success
}

@test "install.sh looks for copy-host-user-conf.sh script" {
    run grep 'copy-host-user-conf.sh' "$INSTALL_SH"
    assert_success
}

# ── image pulling ─────────────────────────────────────────────────────────────

@test "install.sh pulls image before running" {
    run grep 'pull' "$INSTALL_SH"
    assert_success
}

@test "install.sh supports --skip-pull flag" {
    run grep 'SKIP_PULL' "$INSTALL_SH"
    assert_success
}

@test "install.sh checks local image with docker-compatible 'image inspect'" {
    # shellcheck disable=SC2016
    run grep '\$RUNTIME image inspect "\$IMAGE"' "$INSTALL_SH"
    assert_success
}

@test "install.sh does not use podman-only '\$RUNTIME image exists'" {
    # shellcheck disable=SC2016
    run grep '\$RUNTIME image exists' "$INSTALL_SH"
    assert_failure
}

# ── error handling ────────────────────────────────────────────────────────────

@test "install.sh validates container runtime availability" {
    run grep 'info' "$INSTALL_SH"
    assert_success
}

@test "install.sh shows runtime installation instructions" {
    run grep 'show_install_instructions()' "$INSTALL_SH"
    assert_success
}

@test "install.sh requires interactive terminal" {
    run grep '\-t 0' "$INSTALL_SH"
    assert_success
}

# ── script structure ──────────────────────────────────────────────────────────

@test "install.sh uses strict error handling" {
    run grep 'set -euo pipefail' "$INSTALL_SH"
    assert_success
}

@test "install.sh is executable" {
    run test -x "$INSTALL_SH"
    assert_success
}

@test "install.sh has shebang" {
    run head -1 "$INSTALL_SH"
    assert_output "#!/usr/bin/env bash"
}

# ── .vig-os version-pin override (#852) ───────────────────────────────────────

@test "install.sh forwards --version to init-workspace as VIG_OS_VERSION (#852)" {
    # shellcheck disable=SC2016
    run grep -F 'VIG_OS_VERSION=$VERSION' "$INSTALL_SH"
    assert_success
}

# ── upgrade preflight guard (#886) ────────────────────────────────────────────
# `install.sh --force` (the upgrade path) must refuse on protected branches
# (main / dev / release/* prefix / detached HEAD) and on a dirty tree, offer a
# dedicated chore/devkit-upgrade-<version> branch as the way out, and honor
# the single --skip-preflight escape hatch. --smoke-test runs (the headless
# release gate), --preview (report-only) and fresh installs (no --force) are
# exempt. All cases run under --dry-run: a passing guard stops at the printed
# container command (no image pull / container run), and the guard itself
# never mutates the repo under --dry-run.

# git with a fixed identity, no signing — fixtures live outside any workspace
# gitconfig includeIf, so nothing may depend on the host identity setup.
_git() {
    git -c user.email=t@example.com -c user.name=T -c commit.gpgsign=false "$@"
}

# Create a one-commit git repo fixture at $1 on branch $2 (default: an
# allowed feature branch).
_make_repo() {
    local dir="$1" branch="${2:-feature/886-fixture}"
    mkdir -p "$dir"
    _git init -q -b "$branch" "$dir"
    _git -C "$dir" commit -q --allow-empty -m "chore: init"
}

@test "preflight: --force refuses on main with the branch hint (#886)" {
    repo="$BATS_TEST_TMPDIR/on-main"
    _make_repo "$repo" main
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "main"
    assert_output --partial "chore/devkit-upgrade"
    assert_output --partial "--skip-preflight"
}

@test "preflight: --force refuses on dev (#886)" {
    repo="$BATS_TEST_TMPDIR/on-dev"
    _make_repo "$repo" dev
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "dev"
    assert_output --partial "--skip-preflight"
}

@test "preflight: --force refuses on release/* by prefix (#886)" {
    repo="$BATS_TEST_TMPDIR/on-release"
    _make_repo "$repo" release/0.5.0
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "release/0.5.0"
    assert_output --partial "--skip-preflight"
}

@test "preflight: --force refuses on detached HEAD (#886)" {
    repo="$BATS_TEST_TMPDIR/detached"
    _make_repo "$repo"
    _git -C "$repo" checkout -q --detach
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "detached"
    assert_output --partial "--skip-preflight"
}

@test "preflight: --force refuses on a dirty tree (tracked change) (#886)" {
    repo="$BATS_TEST_TMPDIR/dirty-tracked"
    _make_repo "$repo"
    echo "v1" > "$repo/file.txt"
    _git -C "$repo" add file.txt
    _git -C "$repo" commit -q -m "chore: add file"
    echo "v2" >> "$repo/file.txt"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "dirty"
    assert_output --partial "--skip-preflight"
}

@test "preflight: --force refuses on an untracked-unignored file (#886)" {
    repo="$BATS_TEST_TMPDIR/dirty-untracked"
    _make_repo "$repo"
    echo "wip" > "$repo/untracked.txt"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_failure
    assert_output --partial "dirty"
    assert_output --partial "--skip-preflight"
}

@test "preflight: gitignored clutter does not count as dirty (#886)" {
    repo="$BATS_TEST_TMPDIR/ignored-clutter"
    _make_repo "$repo"
    printf '.venv/\n' > "$repo/.gitignore"
    _git -C "$repo" add .gitignore
    _git -C "$repo" commit -q -m "chore: add gitignore"
    mkdir -p "$repo/.venv"
    echo "junk" > "$repo/.venv/junk"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: clean feature branch proceeds (#886)" {
    repo="$BATS_TEST_TMPDIR/clean-feature"
    _make_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: guard works in a git worktree (.git file) (#886)" {
    repo="$BATS_TEST_TMPDIR/wt-parent"
    _make_repo "$repo" main
    wt="$BATS_TEST_TMPDIR/wt-on-dev"
    _git -C "$repo" worktree add -q -b dev "$wt"
    # the fixture really is a linked worktree: .git is a file, not a directory
    run test -f "$wt/.git"
    assert_success
    run bash "$INSTALL_SH" --dry-run --force "$wt" </dev/null
    assert_failure
    assert_output --partial "dev"
    assert_output --partial "--skip-preflight"
}

@test "preflight: clean feature-branch git worktree proceeds (#886)" {
    repo="$BATS_TEST_TMPDIR/wt-parent-ok"
    _make_repo "$repo" main
    wt="$BATS_TEST_TMPDIR/wt-on-feature"
    _git -C "$repo" worktree add -q -b feature/886-wt "$wt"
    run bash "$INSTALL_SH" --dry-run --force "$wt" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: --skip-preflight bypasses branch and tree checks (#886)" {
    repo="$BATS_TEST_TMPDIR/skip-preflight"
    _make_repo "$repo" main
    echo "wip" > "$repo/untracked.txt"
    run bash "$INSTALL_SH" --dry-run --force --skip-preflight "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: --smoke-test is exempt from the guard (#886)" {
    # The downstream smoke-test CI runs `install.sh --version <tag>
    # --smoke-test --force --docker .` headless on a CI checkout — the guard
    # must never gate that release path.
    repo="$BATS_TEST_TMPDIR/smoke-exempt"
    _make_repo "$repo" main
    echo "wip" > "$repo/untracked.txt"
    run bash "$INSTALL_SH" --dry-run --force --smoke-test "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
    assert_output --partial "--smoke-test"
}

@test "preflight: non-git dir refuses non-interactively with a loud warning (#886)" {
    dir="$BATS_TEST_TMPDIR/non-git"
    mkdir -p "$dir"
    touch "$dir/some-file"
    run bash "$INSTALL_SH" --dry-run --force "$dir" </dev/null
    assert_failure
    assert_output --partial "not a git repository"
    assert_output --partial "--skip-preflight"
}

@test "preflight: non-git dir proceeds after explicit confirmation (#886)" {
    dir="$BATS_TEST_TMPDIR/non-git-confirm"
    mkdir -p "$dir"
    touch "$dir/some-file"
    run bash -c "echo y | bash '$INSTALL_SH' --dry-run --force '$dir'"
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: non-git dir aborts when confirmation is declined (#886)" {
    dir="$BATS_TEST_TMPDIR/non-git-decline"
    mkdir -p "$dir"
    touch "$dir/some-file"
    run bash -c "echo n | bash '$INSTALL_SH' --dry-run --force '$dir'"
    assert_failure
    assert_output --partial "--skip-preflight"
}

@test "preflight: dry-run branch offer never mutates the repo (#886)" {
    repo="$BATS_TEST_TMPDIR/offer-dry-run"
    _make_repo "$repo" main
    run bash -c "echo y | bash '$INSTALL_SH' --dry-run --force '$repo'"
    assert_success
    assert_output --partial "Would execute:"
    # accepting the offer under --dry-run must not create/switch branches
    run _git -C "$repo" symbolic-ref --short HEAD
    assert_output "main"
    run _git -C "$repo" branch --list "chore/devkit-upgrade-*"
    assert_output ""
}

@test "preflight: declining the protected-branch offer refuses with the hint (#886)" {
    repo="$BATS_TEST_TMPDIR/offer-decline"
    _make_repo "$repo" main
    run bash -c "echo n | bash '$INSTALL_SH' --dry-run --force '$repo'"
    assert_failure
    assert_output --partial "chore/devkit-upgrade"
    assert_output --partial "--skip-preflight"
}

@test "preflight: fresh install (no --force) is exempt (#886)" {
    dir="$BATS_TEST_TMPDIR/fresh-install"
    mkdir -p "$dir"
    run bash "$INSTALL_SH" --dry-run "$dir" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

# ── --preview forwarding and docs (#886) ──────────────────────────────────────

@test "install.sh forwards --preview to init-workspace.sh (#886)" {
    repo="$BATS_TEST_TMPDIR/preview-forward"
    _make_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --preview "$repo"
    assert_success
    assert_output --partial "--preview"
}

@test "preflight: --preview is exempt from the guard (report-only) (#886)" {
    # A preview never mutates the tree, and #885's destructive mode switches
    # will point users at it first — it must work from any branch/tree state.
    repo="$BATS_TEST_TMPDIR/preview-exempt"
    _make_repo "$repo" main
    echo "wip" > "$repo/untracked.txt"
    run bash "$INSTALL_SH" --dry-run --force --preview "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "help lists --skip-preflight and --preview (#886)" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "--skip-preflight"
    assert_output --partial "--preview"
}

@test "help documents how --preview differs from --dry-run (#886)" {
    run bash "$INSTALL_SH" --help
    assert_success
    # --preview computes the file-level report; --dry-run only prints the
    # container command.
    assert_output --partial "overwrite/preserve/delete"
    assert_output --partial "container command"
}

# ── .vig-os project manifest (#885) ───────────────────────────────────────────
# install.sh reads the persisted delivery mode and identity from the target's
# .vig-os before falling back to defaults (flag > .vig-os > detection/default),
# so `install.sh --force <path>` upgrades a manifest-bearing repo with no
# mode/identity flags. An explicit --mode that contradicts the persisted
# DEVKIT_MODE refuses (mode switching must never happen implicitly).

# Clean feature-branch git fixture carrying a full manifest.
_make_manifest_repo() {
    local dir="$1" mode="${2:-direnv}"
    _make_repo "$dir"
    cat > "$dir/.vig-os" <<MANIFEST
# vig-os devcontainer configuration
DEVCONTAINER_VERSION=0.4.0
DEVKIT_MODE=$mode
DEVKIT_PROJECT=persisted_proj
DEVKIT_ORG=PersistedOrg
DEVKIT_REPO=persisted/repo
MANIFEST
    _git -C "$dir" add .vig-os
    _git -C "$dir" commit -qm "chore: manifest"
}

@test "install.sh reads mode and identity from .vig-os when flags are absent (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-read"
    _make_manifest_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_success
    assert_output --partial '--mode direnv'
    assert_output --partial 'SHORT_NAME=persisted_proj'
    assert_output --partial 'ORG_NAME=PersistedOrg'
    assert_output --partial 'GITHUB_REPOSITORY=persisted/repo'
}

@test "explicit flags override the .vig-os manifest (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-override"
    _make_manifest_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force \
        --name other_name --org OtherOrg --repo other/repo "$repo" </dev/null
    assert_success
    assert_output --partial 'SHORT_NAME=other_name'
    assert_output --partial 'ORG_NAME=OtherOrg'
    assert_output --partial 'GITHUB_REPOSITORY=other/repo'
}

@test "install.sh refuses when --mode conflicts with persisted DEVKIT_MODE (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-conflict"
    _make_manifest_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force --mode both "$repo" </dev/null
    assert_failure
    assert_output --partial 'DEVKIT_MODE'
    assert_output --partial '--preview'
}

@test "a matching --mode proceeds against the persisted DEVKIT_MODE (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-mode-match"
    _make_manifest_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force --mode direnv "$repo" </dev/null
    assert_success
    assert_output --partial '--mode direnv'
}

@test "--preview bypasses the mode-mismatch refusal (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-conflict-preview"
    _make_manifest_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --force --preview --mode both "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "version-only .vig-os leaves install.sh defaults untouched (#885)" {
    repo="$BATS_TEST_TMPDIR/manifest-legacy"
    _make_repo "$repo"
    printf '# vig-os devcontainer configuration\nDEVCONTAINER_VERSION=0.3.9\n' \
        > "$repo/.vig-os"
    _git -C "$repo" add .vig-os
    _git -C "$repo" commit -qm "chore: legacy pin"
    run bash "$INSTALL_SH" --dry-run --force "$repo" </dev/null
    assert_success
    assert_output --partial 'ORG_NAME=vigOS'
    assert_output --partial "SHORT_NAME=manifest_legacy"
}

# ── bare delivery mode (#885) ─────────────────────────────────────────────────

@test "install.sh accepts and forwards --mode bare (#885)" {
    test_dir="$BATS_TEST_TMPDIR/bare-fresh"
    mkdir -p "$test_dir"
    run bash "$INSTALL_SH" --dry-run --mode bare "$test_dir"
    assert_success
    assert_output --partial '--mode bare'
}

@test "help documents the bare mode (#885)" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial 'bare'
}

@test "install.sh skips the host user-conf copy in bare mode (#885)" {
    # Same reasoning as direnv (#738): no .devcontainer/ is scaffolded, so the
    # devcontainer-only host-conf step must not run (or warn misleadingly).
    # shellcheck disable=SC2016
    run grep -E 'MODE" = "direnv" \] \|\| \[ "\$MODE" = "bare"' "$INSTALL_SH"
    assert_success
}
