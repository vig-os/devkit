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

@test "help flag (-h and --help) exits 0 and prints usage" {
    for flag in -h --help; do
        echo "flag: $flag"
        run bash "$INSTALL_SH" "$flag"
        assert_success
        assert_output --partial "vigOS Devcontainer Install Script"
        assert_output --partial "USAGE:"
        assert_output --partial "OPTIONS:"
    done
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

# ── runtime auto-detection order (#1305) ──────────────────────────────────────
# ubuntu-latest runners pair a preinstalled podman with a stale system crun
# that rejects podman >= 5's OCI configs ("crun: unknown version specified"),
# so with both runtimes on PATH auto-detection must prefer a docker whose
# daemon responds — the #1299 regression on the consumer side, where the
# setup-env crun pin does not apply. Podman-only hosts are unchanged, and a
# dead docker daemon still falls back to podman. Explicit --docker/--podman
# keep overriding. Exercised end to end against PATH stubs (nothing pulled).
_run_install_autodetect() {
    local dir="$1" docker_stub="$2"
    local stub="$BATS_TEST_TMPDIR/stub-rt"
    rm -rf "$stub"
    mkdir -p "$stub"
    printf '%s\n' "$docker_stub" >"$stub/docker"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/podman"
    chmod +x "$stub/docker" "$stub/podman"
    _make_repo "$dir"
    run env PATH="$stub:$PATH" bash "$INSTALL_SH" \
        --skip-pull --mode direnv "$dir" </dev/null
}

@test "auto-detection prefers docker with a responsive daemon over podman (#1305)" {
    _run_install_autodetect "$BATS_TEST_TMPDIR/rt-docker" \
        '#!/usr/bin/env bash
exit 0'
    assert_success
    assert_output --partial "Using docker"
}

@test "auto-detection falls back to podman when the docker daemon is dead (#1305)" {
    # shellcheck disable=SC2016  # stub body is a literal script, no expansion
    _run_install_autodetect "$BATS_TEST_TMPDIR/rt-podman" \
        '#!/usr/bin/env bash
[ "$1" = "info" ] && exit 1
exit 0'
    assert_success
    assert_output --partial "Using podman"
}

# ── os detection ──────────────────────────────────────────────────────────────

@test "install.sh detect_os covers macOS and the Linux distro families" {
    # Structural-only coverage: detect_os keys install instructions off uname /
    # /etc/os-release, which a test cannot vary. One looped grep per family.
    local patterns=(
        'Darwin\*'
        'ubuntu|debian|pop|linuxmint'
        'fedora|rhel|centos|rocky|almalinux'
        'arch|manjaro|endeavouros'
        'opensuse\*|sles'
    )
    for pattern in "${patterns[@]}"; do
        echo "pattern: $pattern"
        run grep "$pattern" "$INSTALL_SH"
        assert_success
    done
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

# ── git repository setup (embedded in install.sh) ────────────────────────────
# The git phase (init, initial commit, branch creation) is exercised end to end
# in tests/test_install_script.py::TestInstallScriptIntegration (e.g.
# test_install_creates_git_repository, test_install_git_branches) against a
# real scaffold; only pins with no pytest twin live here.

@test "install.sh guards the scaffold commit against a populated directory" {
    # The automatic 'initial project scaffold' commit must only run for a
    # freshly scaffolded (empty) target, gated by the TARGET_WAS_EMPTY flag,
    # so it never sweeps a pre-populated directory into a misleading commit (#759).
    # shellcheck disable=SC2016
    run grep 'TARGET_WAS_EMPTY' "$INSTALL_SH"
    assert_success
}

# ── workflow model: trunk skips the dev branch (#1205) ────────────────────────
# The gitflow default carries a long-lived 'dev' branch; the trunk workflow
# model works straight on 'main'. The branch-skip behavior is proven end to end
# in test_install_script.py::test_install_trunk_creates_main_only; --dry-run
# proves the --workflow flag is forwarded to the container command.

@test "install.sh --dry-run --workflow trunk forwards --workflow to init-workspace (#1205)" {
    mkdir -p "$BATS_TEST_TMPDIR/wf-trunk"
    run bash "$INSTALL_SH" --dry-run --workflow trunk "$BATS_TEST_TMPDIR/wf-trunk" </dev/null
    assert_success
    assert_output --partial "Would execute:"
    assert_output --partial "--workflow trunk"
}

@test "install.sh --dry-run without --workflow forwards no workflow flag (gitflow default) (#1205)" {
    mkdir -p "$BATS_TEST_TMPDIR/wf-default"
    run bash "$INSTALL_SH" --dry-run "$BATS_TEST_TMPDIR/wf-default" </dev/null
    assert_success
    assert_output --partial "Would execute:"
    refute_output --partial "--workflow"
}

@test "install.sh rejects an invalid --workflow value (#1205)" {
    mkdir -p "$BATS_TEST_TMPDIR/wf-bogus"
    run bash "$INSTALL_SH" --dry-run --workflow bogus "$BATS_TEST_TMPDIR/wf-bogus" </dev/null
    assert_failure
    assert_output --partial "Invalid --workflow"
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

@test "install.sh shows runtime installation instructions" {
    run grep 'show_install_instructions()' "$INSTALL_SH"
    assert_success
}

@test "install.sh requires interactive terminal" {
    run grep '\-t 0' "$INSTALL_SH"
    assert_success
}

# ── script structure ──────────────────────────────────────────────────────────
# (executable bit is pinned by test_utils.py::test_script_exists_and_executable)

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
    # A realistic topic-branch checkout has a `main` alongside it. The
    # default-branch preflight (#1283) refuses a non-main default only when no
    # `main` exists anywhere, so give every non-main fixture a `main` branch —
    # the gitflow accept-path — leaving the #886 guard's assertions unchanged.
    [ "$branch" = main ] || _git -C "$dir" branch main
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

# ── default-branch preflight (#1283) ──────────────────────────────────────────
# Scaffolding assumes the default branch is `main` (the branch-name hook, ci.yml
# and its workflow triggers all key off it). On a legacy `master` repo the
# scaffold would succeed silently, then block every commit. A preflight detects a
# non-`main` default branch and aborts BEFORE anything is written, with the
# rename recipe. Unlike the #886 guard it runs on fresh installs too;
# --skip-preflight and --smoke-test skip it, --preview only warns, and a `main`
# default (or a topic/dev branch of a repo that has `main`) proceeds unchanged.

# A repo whose default branch is `master` via origin/HEAD, with no `main`
# anywhere. Not built through _make_repo (which would add a `main`).
_make_master_origin_repo() {
    local work="$1" origin="$1.origin.git"
    _git init -q -b master --bare "$origin"
    mkdir -p "$work"
    _git init -q -b master "$work"
    _git -C "$work" commit -q --allow-empty -m "chore: init"
    _git -C "$work" remote add origin "$origin"
    _git -C "$work" push -q origin master
    _git -C "$work" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/master
}

# A local-only repo (no origin) checked out on `master`, no `main`.
_make_local_master_repo() {
    local dir="$1"
    mkdir -p "$dir"
    _git init -q -b master "$dir"
    _git -C "$dir" commit -q --allow-empty -m "chore: init"
}

@test "preflight: master default via origin/HEAD aborts pre-copy with rename recipe (#1283)" {
    repo="$BATS_TEST_TMPDIR/master-origin"
    _make_master_origin_repo "$repo"
    run bash "$INSTALL_SH" --dry-run "$repo" </dev/null
    assert_failure
    assert_output --partial "git branch -m master main && git push -u origin main"
    assert_output --partial "gh repo edit --default-branch main"
    assert_output --partial "MIGRATION.md"
    # aborts before the copy step: never reaches the container command
    refute_output --partial "Would execute:"
}

@test "preflight: main default proceeds unchanged (#1283)" {
    repo="$BATS_TEST_TMPDIR/main-default-1283"
    _make_repo "$repo" main
    run bash "$INSTALL_SH" --dry-run "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: --skip-preflight proceeds on a master repo (#1283)" {
    repo="$BATS_TEST_TMPDIR/master-skip-1283"
    _make_local_master_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --skip-preflight "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: --preview warns on a master repo without aborting (#1283)" {
    repo="$BATS_TEST_TMPDIR/master-preview-1283"
    _make_local_master_repo "$repo"
    run bash "$INSTALL_SH" --dry-run --preview "$repo" </dev/null
    assert_success
    assert_output --partial "not 'main'"
    assert_output --partial "Would execute:"
}

@test "preflight: dev branch of a repo that has main proceeds (#1283)" {
    repo="$BATS_TEST_TMPDIR/gitflow-dev-1283"
    mkdir -p "$repo"
    _git init -q -b main "$repo"
    _git -C "$repo" commit -q --allow-empty -m "chore: init"
    _git -C "$repo" checkout -q -b dev
    run bash "$INSTALL_SH" --dry-run "$repo" </dev/null
    assert_success
    assert_output --partial "Would execute:"
}

@test "preflight: local-only master repo (no origin) aborts with the same guidance (#1283)" {
    repo="$BATS_TEST_TMPDIR/master-local-1283"
    _make_local_master_repo "$repo"
    run bash "$INSTALL_SH" --dry-run "$repo" </dev/null
    assert_failure
    assert_output --partial "git branch -m master main && git push -u origin main"
    assert_output --partial "gh repo edit --default-branch main"
    refute_output --partial "Would execute:"
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

# ── opt-in .devcontainer/ prune forwarding (#990) ─────────────────────────────

@test "install.sh forwards --prune-devcontainer to init-workspace.sh (#990)" {
    repo="$BATS_TEST_TMPDIR/prune-forward"
    _make_manifest_repo "$repo" direnv
    run bash "$INSTALL_SH" --dry-run --force --prune-devcontainer "$repo" </dev/null
    assert_success
    assert_output --partial "--prune-devcontainer"
}

@test "help lists --prune-devcontainer (#990)" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "--prune-devcontainer"
}

@test "help lists --skip-pull (#1008)" {
    run bash "$INSTALL_SH" --help
    assert_success
    assert_output --partial "--skip-pull"
}

# ── mode-aware "Next steps" (#1015) ───────────────────────────────────────────
# The printed next step must match the delivery mode: only the container modes
# scaffold a .devcontainer/ for VS Code to detect, so direnv must be pointed at
# the direnv entrypoint instead. Exercised end to end against a stub runtime
# (`docker` on PATH, exit 0 for info/inspect/run) so nothing is pulled or
# scaffolded and the run still reaches the final message.
_run_install_stubbed() {
    local dir="$1" mode="$2"
    local stub="$BATS_TEST_TMPDIR/stub-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/docker"
    chmod +x "$stub/docker"
    _make_repo "$dir"
    run env PATH="$stub:$PATH" bash "$INSTALL_SH" \
        --docker --skip-pull --mode "$mode" "$dir" </dev/null
}

@test "direnv install points at the direnv entrypoint, not VS Code (#1015)" {
    _run_install_stubbed "$BATS_TEST_TMPDIR/next-direnv" direnv
    assert_success
    refute_output --partial "Open in VS Code"
    assert_output --partial "direnv allow"
    assert_output --partial "nix develop"
}

@test "bare install still points at 'just help' (#1015)" {
    _run_install_stubbed "$BATS_TEST_TMPDIR/next-bare" bare
    assert_success
    refute_output --partial "Open in VS Code"
    assert_output --partial "just help"
}

@test "devcontainer install still points at VS Code (#1015)" {
    _run_install_stubbed "$BATS_TEST_TMPDIR/next-devcontainer" devcontainer
    assert_success
    assert_output --partial "Open in VS Code"
}

@test "both install points at VS Code and mentions direnv (#1015)" {
    _run_install_stubbed "$BATS_TEST_TMPDIR/next-both" both
    assert_success
    assert_output --partial "Open in VS Code"
    assert_output --partial "direnv allow"
}

# ── docker ownership repair before the git phase (#1235) ──────────────────────
# Under docker the scaffold container runs as root, so the bind-mounted output
# lands root-owned and the host-side git phase (setup_git_repo) can't write to
# it — warn-not-fail by design, so the installer "succeeds" leaving a root-owned,
# git-less tree. install.sh must chown the tree back to the invoking user via a
# throwaway container BEFORE the git phase. Rootless podman maps container-root
# to the invoking user, so it needs no repair. Exercised against a logging stub
# runtime (records each invocation) so nothing is pulled or actually chowned.
# The repair keys on the OBSERVED post-scaffold ownership, not the runtime name
# (#1248): pass owned=foreign to simulate a tree with files not owned by the
# invoking user (real docker's root-owned output) — an unprivileged test can't
# create root-owned files, so a stub of install.sh's find(1) ownership probe
# reporting a hit stands in for them (install.sh runs no other find).
_run_install_logging_stub() {
    local dir="$1" runtime="$2" log="$3" owned="${4:-user}"
    local stub="$BATS_TEST_TMPDIR/stub-$runtime"
    mkdir -p "$stub"
    cat >"$stub/$runtime" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$log"
exit 0
STUB
    chmod +x "$stub/$runtime"
    if [ "$owned" = "foreign" ]; then
        cat >"$stub/find" <<'STUB'
#!/usr/bin/env bash
echo "/workspace/root-owned-file"
STUB
        chmod +x "$stub/find"
    fi
    _make_repo "$dir"
    run env PATH="$stub:$PATH" bash "$INSTALL_SH" \
        "--$runtime" --skip-pull --mode direnv "$dir" </dev/null
}

@test "docker path chowns scaffold output to the invoking user (#1235)" {
    log="$BATS_TEST_TMPDIR/docker-repair.log"
    _run_install_logging_stub "$BATS_TEST_TMPDIR/repair-docker" docker "$log" foreign
    assert_success
    run grep -F "chown -R $(id -u):$(id -g) /workspace" "$log"
    assert_success
}

@test "podman path runs no ownership-repair container (#1235)" {
    log="$BATS_TEST_TMPDIR/podman-repair.log"
    _run_install_logging_stub "$BATS_TEST_TMPDIR/repair-podman" podman "$log"
    assert_success
    run grep -F "chown -R" "$log"
    assert_failure
}

@test "docker path skips the ownership repair on an already-user-owned tree (#1248)" {
    # Rootless podman behind a docker CLI compat shim maps container-root to
    # the invoking user, so the scaffold output is already correctly owned;
    # running the repair chown inside such a container would flip the tree to
    # an unmapped subuid (#1248). The logging stub scaffold writes nothing, so
    # the fixture tree stays user-owned — the repair container must not run.
    log="$BATS_TEST_TMPDIR/docker-skip.log"
    _run_install_logging_stub "$BATS_TEST_TMPDIR/repair-skip" docker "$log"
    assert_success
    run grep -F "chown -R" "$log"
    assert_failure
}

@test "ownership repair is ordered before the git phase on the docker path (#1235)" {
    # The chown container run must appear ahead of the setup_git_repo invocation
    # in source, so the host-side git phase writes to a user-owned tree (#1235).
    chown_line="$(grep -n 'chown -R' "$INSTALL_SH" | head -1 | cut -d: -f1)"
    git_line="$(grep -n 'if ! setup_git_repo' "$INSTALL_SH" | head -1 | cut -d: -f1)"
    [ -n "$chown_line" ]
    [ -n "$git_line" ]
    [ "$chown_line" -lt "$git_line" ]
}

# ── floating vigos flake-lock advance on upgrade (#1263) ──────────────────────
# A --force upgrade advances .vig-os DEVKIT_VERSION (the scaffold + image), but
# a FLOATING `vigos` input's dev shell is governed by flake.lock, which stays
# wherever the last `nix flake update vigos` left it — so direnv consumers
# silently keep running the previous release's toolchain (vig-utils, hook
# sets). install.sh must advance the lock HOST-SIDE after the scaffold (the
# container must not write it: network dependence + ownership hazards,
# #1235/#1248) when the workspace is a direnv/both consumer with a floating
# input and an existing flake.lock. Pinned (?ref=) inputs stay the consumer's
# explicit choice (covered by the #1093 scaffold warning); a missing lock
# (fresh scaffold) locks current content on first shell entry anyway.
# Exercised against a stub `docker` (scaffold no-op) + logging stub `nix`.

# Build an upgradeable consumer fixture at $1: clean feature-branch repo with a
# .vig-os manifest (mode $4, default direnv), a flake.nix whose vigos input is
# $2 (a full `vigos.url = ...` line), and — unless $3=nolock — a flake.lock.
_make_flake_workspace() {
    local dir="$1" url_line="$2" with_lock="${3:-lock}" mode="${4:-direnv}"
    _make_repo "$dir"
    printf 'DEVKIT_VERSION=1.4.1\nDEVKIT_MODE=%s\n' "$mode" >"$dir/.vig-os"
    cat >"$dir/flake.nix" <<FLAKE
{
  inputs = {
    #   vigos.url = "github:vig-os/devkit?ref=<tag>";
    $url_line
    nixpkgs.follows = "vigos/nixpkgs";
  };
}
FLAKE
    if [ "$with_lock" = "lock" ]; then
        echo '{}' >"$dir/flake.lock"
    fi
    _git -C "$dir" add -A
    _git -C "$dir" commit -q -m "chore: fixture"
}

# Run install.sh against stub docker + a logging stub nix (exit code $3).
# Extra install.sh args (e.g. --force) follow.
_run_install_nix_stub() {
    local dir="$1" nixlog="$2" nix_exit="${3:-0}"
    shift 3
    local stub="$BATS_TEST_TMPDIR/stub-flake-bin"
    mkdir -p "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/docker"
    chmod +x "$stub/docker"
    cat >"$stub/nix" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$nixlog"
exit $nix_exit
STUB
    chmod +x "$stub/nix"
    run env PATH="$stub:$PATH" bash "$INSTALL_SH" --docker --skip-pull "$@" "$dir" </dev/null
}

@test "upgrade advances a floating vigos flake lock (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-floating"
    log="$BATS_TEST_TMPDIR/flake-floating-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    run grep -F "flake update vigos --flake $dir" "$log"
    assert_success
}

@test "upgrade leaves a pinned vigos input alone (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-pinned"
    log="$BATS_TEST_TMPDIR/flake-pinned-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit?ref=1.4.1";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    run grep -F "flake update" "$log"
    assert_failure
}

@test "upgrade without a flake.lock skips the advance (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-nolock"
    log="$BATS_TEST_TMPDIR/flake-nolock-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";' nolock
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    run grep -F "flake update" "$log"
    assert_failure
}

@test "fresh install (no --force) runs no lock advance (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-fresh"
    log="$BATS_TEST_TMPDIR/flake-fresh-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";'
    _run_install_nix_stub "$dir" "$log" 0
    assert_success
    run grep -F "flake update" "$log"
    assert_failure
}

@test "devcontainer-mode upgrade runs no lock advance (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-container-mode"
    log="$BATS_TEST_TMPDIR/flake-container-mode-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";' lock devcontainer
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    run grep -F "flake update" "$log"
    assert_failure
}

@test "failed lock advance is non-fatal and prints the manual step (#1263)" {
    dir="$BATS_TEST_TMPDIR/flake-fail"
    log="$BATS_TEST_TMPDIR/flake-fail-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";'
    _run_install_nix_stub "$dir" "$log" 1 --force
    assert_success
    assert_output --partial "nix flake update vigos"
}

# ── name-agnostic devkit input discovery + loud skip (#1497) ──────────────────
# flake.nix is a PRESERVE_FILE, so the consumer's devkit input may be named
# anything and may pin a ref in either form (?ref=X, or the /X path suffix the
# field case used). The #1263 advance was guarded by a grep matching only an
# input literally named `vigos` at the unpinned URL — every other spelling was
# skipped with no message at all, so the weekly upgrade reported success while
# the flake input (where the Rust pack lives entirely) stayed frozen. The
# advance is now keyed on the URL, not the name, and EVERY outcome prints a
# `flake-bump:` line the upgrade workflow surfaces in the adoption PR.

@test "upgrade advances a floating input named devkit (#1497)" {
    dir="$BATS_TEST_TMPDIR/flake-renamed"
    log="$BATS_TEST_TMPDIR/flake-renamed-nix.log"
    _make_flake_workspace "$dir" 'devkit.url = "github:vig-os/devkit";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    assert_output --partial "flake-bump: advanced"
    run grep -F "flake update devkit --flake $dir" "$log"
    assert_success
}

@test "the floating vigos advance reports flake-bump: advanced (#1497)" {
    dir="$BATS_TEST_TMPDIR/flake-report-advanced"
    log="$BATS_TEST_TMPDIR/flake-report-advanced-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    assert_output --partial "flake-bump: advanced"
}

@test "a path-ref pinned input is left alone but reported (#1497)" {
    dir="$BATS_TEST_TMPDIR/flake-path-ref"
    log="$BATS_TEST_TMPDIR/flake-path-ref-nix.log"
    _make_flake_workspace "$dir" 'devkit.url = "github:vig-os/devkit/dev";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    assert_output --partial "flake-bump: skipped"
    assert_output --partial "dev"
    run grep -F "flake update" "$log"
    assert_failure
}

@test "a ?ref= pinned input reports the skip (#1497)" {
    dir="$BATS_TEST_TMPDIR/flake-qref-report"
    log="$BATS_TEST_TMPDIR/flake-qref-report-nix.log"
    _make_flake_workspace "$dir" 'vigos.url = "github:vig-os/devkit?ref=1.4.1";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    assert_output --partial "flake-bump: skipped"
    assert_output --partial "1.4.1"
    run grep -F "flake update" "$log"
    assert_failure
}

@test "no recognized devkit input reports it and advances nothing (#1497)" {
    dir="$BATS_TEST_TMPDIR/flake-no-input"
    log="$BATS_TEST_TMPDIR/flake-no-input-nix.log"
    _make_flake_workspace "$dir" 'scitadel.url = "github:vig-os/scitadel";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    assert_output --partial "flake-bump: no devkit input"
    run grep -F "flake update" "$log"
    assert_failure
}

@test "the doc-comment example never counts as the devkit input (#1497)" {
    # _make_flake_workspace always writes the commented example line above the
    # real input; with no real devkit input present, the comment alone must not
    # trigger an advance or a pinned-skip report.
    dir="$BATS_TEST_TMPDIR/flake-comment-only"
    log="$BATS_TEST_TMPDIR/flake-comment-only-nix.log"
    _make_flake_workspace "$dir" 'scitadel.url = "github:vig-os/scitadel";'
    _run_install_nix_stub "$dir" "$log" 0 --force
    assert_success
    refute_output --partial "flake-bump: skipped"
    run grep -F "flake update" "$log"
    assert_failure
}
