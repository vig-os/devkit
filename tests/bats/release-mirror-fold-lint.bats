#!/usr/bin/env bats
# BATS tests: the DEVKIT_SYNC_TARGET mirror-fold render must LINT inside a
# consumer repo (#1531).
#
# The sibling files cover the other two halves of this render: init-workspace.bats
# pins that the fold steps are RENDERED, release-mirror-fold.bats EXECUTES the
# rendered `run:` blocks. Neither looks at the rendered tree the way a consumer's
# own hooks do — and the fold block has exactly one consumer in the org, so a
# lint regression inside it is discovered by that consumer's scheduled upgrade,
# in production (#1529).
#
# Two lints, over a fully rendered mirror-mode workspace in both workflow models:
#
#   typos      — with NO allowlist at all (`--isolated`, no `--config`). A
#                consumer's `.typos.toml` is seeded once and never overwritten by
#                an upgrade, so generated content may not rely on ANY entry in
#                it: not one devkit later added to its own config (#1488's `mis`,
#                which is exactly what broke the org-config upgrade in #1529),
#                and not one the current seed happens to carry, because the
#                consumer's copy predates it. `--hidden` is needed because the
#                interesting files live under the dot-directory `.github/`, which
#                typos' tree walk skips by default (a consumer's hook never
#                walks: prek hands it the file list).
#   actionlint — over the rendered workflows. The existing per-mode actionlint
#                fixtures render the DEFAULT path; the fold injects steps into
#                release-core.yml and a whole job into promote-release.yml, which
#                nothing linted before.
#
# The workspace is rendered in `direnv` mode, the shape of the sole mirror-mode
# consumer. A devcontainer-mode tree additionally ships `.devcontainer/` — the
# synced devkit CHANGELOG and `version-check.sh` — whose prose does lean on seed
# entries (`Nd`, `passt`, and released changelog text that may never be edited).
# Whether the seed should carry words for those at all is the open question in
# #1529, not the subject of this pin.

setup() {
    load test_helper
    MIRROR_GITFLOW="$BATS_FILE_TMPDIR/mirror-gitflow"
    MIRROR_TRUNK="$BATS_FILE_TMPDIR/mirror-trunk"
}

# Render both mirror-mode workspaces ONCE for the whole file: the tests only
# lint the rendered trees, and scaffold+upgrade is the slow part.
setup_file() {
    local root
    root="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    _render_mirror "$root" gitflow "$BATS_FILE_TMPDIR/mirror-gitflow" || return 1
    _render_mirror "$root" trunk "$BATS_FILE_TMPDIR/mirror-trunk" || return 1
}

# Render a mirror-mode consumer workspace for workflow model $2 into $3.
# Mirror mode is not a scaffold flag: the manifest key is set on the scaffolded
# workspace and a second (upgrade) pass injects the fold block, which is how a
# consumer reaches this state.
_render_mirror() {
    local root="$1" model="$2" ws="$3"
    local stub="$BATS_FILE_TMPDIR/stub-bin"
    mkdir -p "$ws" "$stub"
    printf '#!/usr/bin/env bash\nexit 0\n' >"$stub/just"
    chmod +x "$stub/just"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$root/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        SHORT_NAME=testproj \
        GITHUB_REPOSITORY=test/repo \
        bash "$root/assets/init-workspace.sh" --force --no-prompts \
        --mode direnv --workflow "$model" \
        >"$ws.log" 2>&1 || { cat "$ws.log" >&2; return 1; }
    sed -i 's#^DEVKIT_SYNC_TARGET=.*#DEVKIT_SYNC_TARGET=sync/issue-mirror#' "$ws/.vig-os"
    env PATH="$stub:$PATH" \
        TEMPLATE_DIR="$root/assets/workspace" \
        WORKSPACE_DIR="$ws" \
        bash "$root/assets/init-workspace.sh" --force --no-prompts \
        >>"$ws.log" 2>&1 || { cat "$ws.log" >&2; return 1; }
    # Fixture precondition, not a test: without the fold block the lints below
    # would pass over a workspace that never rendered it — green and vacuous.
    local rc="$ws/.github/workflows/release-core.yml"
    grep -qF 'name: Stage sync mirror archive for fold' "$rc" ||
        { echo "$model render: fold steps missing from release-core.yml" >&2; return 1; }
    grep -qF -- '-f "target-branch=sync/issue-mirror"' "$rc" ||
        { echo "$model render: sync dispatch not retargeted to the mirror" >&2; return 1; }
    # actionlint resolves `./.github/workflows/<reusable>` against the git root,
    # so it needs one — a real consumer repo is a git repo.
    git -C "$ws" init -q
}

# typos as a consumer with an untouched seed would see it: no allowlist.
_typos_strict() { (cd "$1" && typos --hidden --isolated); }

_actionlint() { (cd "$1" && actionlint); }

@test "the gitflow mirror-fold render is typos-clean with no allowlist (#1529)" {
    run _typos_strict "$MIRROR_GITFLOW"
    assert_success
}

@test "the trunk mirror-fold render is typos-clean with no allowlist (#1529)" {
    run _typos_strict "$MIRROR_TRUNK"
    assert_success
}

@test "actionlint passes over the gitflow mirror-fold render (#1531)" {
    run _actionlint "$MIRROR_GITFLOW"
    assert_success
}

@test "actionlint passes over the trunk mirror-fold render (#1531)" {
    run _actionlint "$MIRROR_TRUNK"
    assert_success
}
